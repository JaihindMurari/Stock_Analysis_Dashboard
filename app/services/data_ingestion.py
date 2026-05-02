"""
Data Ingestion Service
Fetches OHLCV data from yfinance and persists it to MySQL.
Handles batch fetching, deduplication, and error recovery.
"""
import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app import db
from app.models import Stock, Price, Indicator, Signal
from app.utils.stock_universe import NSE_TOP_50
from app.services.indicators import compute_all_indicators, generate_signal

logger = logging.getLogger(__name__)


# ── Stock universe seeding ─────────────────────────────────────────────────────

def seed_stock_universe():
    """Populate the stocks table from the static universe list (idempotent)."""
    added = 0
    for symbol, name, sector, industry in NSE_TOP_50:
        existing = Stock.query.filter_by(symbol=symbol).first()
        if not existing:
            s = Stock(symbol=symbol, name=name, sector=sector,
                      industry=industry, exchange='NSE')
            db.session.add(s)
            added += 1
    db.session.commit()
    logger.info("Stock universe seeded — %d new rows added.", added)


# ── Single-stock data fetch ────────────────────────────────────────────────────

def fetch_stock_history(symbol: str, days: int = 365) -> pd.DataFrame:
    """
    Fetch historical daily OHLCV data for one symbol.
    Returns empty DataFrame on failure.
    """
    try:
        ticker = yf.Ticker(symbol)
        end    = datetime.utcnow()
        start  = end - timedelta(days=days)
        df = ticker.history(start=start.strftime('%Y-%m-%d'),
                            end=end.strftime('%Y-%m-%d'),
                            interval='1d', auto_adjust=True, actions=False)
        if df.empty:
            logger.warning("No data returned for %s", symbol)
            return pd.DataFrame()

        df.reset_index(inplace=True)
        df.columns = [c.lower() for c in df.columns]
        df.rename(columns={'date': 'datetime'}, inplace=True)
        # Ensure datetime is tz-naive
        if hasattr(df['datetime'].dtype, 'tz') and df['datetime'].dt.tz is not None:
            df['datetime'] = df['datetime'].dt.tz_localize(None)
        return df[['datetime', 'open', 'high', 'low', 'close', 'volume']]
    except Exception as exc:
        logger.error("Error fetching %s: %s", symbol, exc)
        return pd.DataFrame()


def fetch_latest_quote(symbol: str) -> dict | None:
    """Fetch the most recent day's price info for quick summary cards."""
    try:
        ticker = yf.Ticker(symbol)
        info   = ticker.fast_info
        return {
            'last_price':  getattr(info, 'last_price', None),
            'open':        getattr(info, 'open', None),
            'day_high':    getattr(info, 'day_high', None),
            'day_low':     getattr(info, 'day_low', None),
            'volume':      getattr(info, 'three_month_average_volume', None),
            'market_cap':  getattr(info, 'market_cap', None),
            'prev_close':  getattr(info, 'previous_close', None),
        }
    except Exception as exc:
        logger.debug("fast_info failed for %s: %s", symbol, exc)
        return None


# ── Persistence ────────────────────────────────────────────────────────────────

def upsert_prices(stock: Stock, df: pd.DataFrame):
    """
    Bulk-upsert OHLCV rows.  ON DUPLICATE KEY UPDATE ensures no duplicates.
    """
    if df.empty:
        return 0

    rows = [
        {
            'stock_id': stock.id,
            'datetime': row.datetime,
            'open':     round(float(row.open),   4) if row.open   else None,
            'high':     round(float(row.high),   4) if row.high   else None,
            'low':      round(float(row.low),    4) if row.low    else None,
            'close':    round(float(row.close),  4) if row.close  else None,
            'volume':   int(row.volume)              if row.volume else None,
            'adj_close':round(float(row.close),  4) if row.close  else None,
        }
        for row in df.itertuples(index=False)
    ]

    stmt = mysql_insert(Price).values(rows)
    stmt = stmt.on_duplicate_key_update(
        open=stmt.inserted.open, high=stmt.inserted.high,
        low=stmt.inserted.low,   close=stmt.inserted.close,
        volume=stmt.inserted.volume,
    )
    db.session.execute(stmt)
    db.session.commit()
    return len(rows)


def upsert_indicators(stock: Stock, df: pd.DataFrame):
    """Compute indicators on the full price series and bulk-upsert."""
    if len(df) < 26:          # need at least 26 rows for MACD
        return 0

    df = df.copy().sort_values('datetime').reset_index(drop=True)
    df = compute_all_indicators(df)

    ind_cols = ['sma_20','sma_50','sma_200','ema_12','ema_26',
                'rsi','macd','macd_signal','macd_hist',
                'bb_upper','bb_middle','bb_lower']

    def _safe(v):
        import math
        if v is None: return None
        try:
            f = float(v)
            return None if math.isnan(f) or math.isinf(f) else round(f, 6)
        except (TypeError, ValueError):
            return None

    rows = []
    for row in df.itertuples(index=False):
        rows.append({
            'stock_id': stock.id,
            'datetime': row.datetime,
            **{col: _safe(getattr(row, col, None)) for col in ind_cols},
        })

    stmt = mysql_insert(Indicator).values(rows)
    stmt = stmt.on_duplicate_key_update(
        **{col: getattr(stmt.inserted, col) for col in ind_cols}
    )
    db.session.execute(stmt)
    db.session.commit()
    return len(rows)


def upsert_signal(stock: Stock, df: pd.DataFrame):
    """Generate and upsert the latest signal row."""
    if df.empty:
        return

    df = df.copy().sort_values('datetime').reset_index(drop=True)
    df = compute_all_indicators(df)
    latest = df.iloc[-1].to_dict()
    sig    = generate_signal(latest)

    stmt = mysql_insert(Signal).values(
        stock_id=stock.id, datetime=latest['datetime'],
        signal_type=sig['signal_type'], confidence=sig['confidence'],
        reason=sig['reason'],
    )
    stmt = stmt.on_duplicate_key_update(
        signal_type=stmt.inserted.signal_type,
        confidence=stmt.inserted.confidence,
        reason=stmt.inserted.reason,
    )
    db.session.execute(stmt)
    db.session.commit()


# ── Orchestrators ──────────────────────────────────────────────────────────────

def refresh_single_stock(stock: Stock, days: int = 365):
    """Full refresh for one stock: prices → indicators → signal."""
    logger.info("Refreshing %s …", stock.symbol)
    df = fetch_stock_history(stock.symbol, days=days)
    if df.empty:
        return

    p_count = upsert_prices(stock, df)
    i_count = upsert_indicators(stock, df)
    upsert_signal(stock, df)

    # Update market_cap from fast_info
    quote = fetch_latest_quote(stock.symbol)
    if quote and quote.get('market_cap'):
        stock.market_cap = int(quote['market_cap'])
        db.session.commit()

    logger.info("  %s — %d price rows, %d indicator rows stored.",
                stock.symbol, p_count, i_count)


def refresh_all_stocks(days: int = 365):
    """Iterate over all active stocks and refresh each one."""
    stocks = Stock.query.filter_by(is_active=True).all()
    logger.info("Starting full refresh for %d stocks …", len(stocks))
    for stock in stocks:
        try:
            refresh_single_stock(stock, days=days)
        except Exception as exc:
            logger.error("Failed to refresh %s: %s", stock.symbol, exc)
            db.session.rollback()
    logger.info("Full refresh complete.")


def incremental_update():
    """Light update — fetch only last 5 days to keep indicators current."""
    refresh_all_stocks(days=5)
