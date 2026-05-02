"""
API Blueprint — REST endpoints for the NSE Dashboard.

GET /api/stocks                  → all tracked stocks with latest quote
GET /api/stock/<symbol>          → detailed metrics + price history + indicators
GET /api/stock/<symbol>/history  → OHLCV history (query: days=90)
GET /api/signals                 → latest signal for every stock
GET /api/top-movers              → top-5 gainers and losers
GET /api/market-summary          → aggregate market stats
POST /api/admin/refresh          → trigger full data refresh
POST /api/admin/seed             → seed stock universe
"""
import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import desc, func

from app import db
from app.models import Stock, Price, Indicator, Signal

api_bp  = Blueprint('api', __name__)
logger  = logging.getLogger(__name__)


def _ok(data, **kwargs):
    return jsonify({'status': 'ok', 'data': data, **kwargs})

def _err(msg, code=400):
    return jsonify({'status': 'error', 'message': msg}), code


# ── /api/stocks ────────────────────────────────────────────────────────────────

@api_bp.route('/stocks')
def list_stocks():
    """Return all active stocks with their latest price snapshot."""
    stocks = Stock.query.filter_by(is_active=True).order_by(Stock.symbol).all()
    result = []
    for s in stocks:
        latest = (Price.query
                  .filter_by(stock_id=s.id)
                  .order_by(desc(Price.datetime))
                  .first())
        prev = (Price.query
                .filter_by(stock_id=s.id)
                .order_by(desc(Price.datetime))
                .offset(1).first())
        sig = (Signal.query
               .filter_by(stock_id=s.id)
               .order_by(desc(Signal.datetime))
               .first())

        close      = float(latest.close)      if latest and latest.close else None
        prev_close = float(prev.close)        if prev   and prev.close   else None
        change     = round(close - prev_close, 2)          if close and prev_close else None
        change_pct = round((change / prev_close) * 100, 2) if change and prev_close else None

        result.append({
            **s.to_dict(),
            'close':      close,
            'high':       float(latest.high)   if latest and latest.high   else None,
            'low':        float(latest.low)    if latest and latest.low    else None,
            'volume':     latest.volume        if latest else None,
            'prev_close': prev_close,
            'change':     change,
            'change_pct': change_pct,
            'signal':     sig.signal_type      if sig else None,
            'confidence': float(sig.confidence) if sig and sig.confidence else None,
            'last_updated': latest.datetime.isoformat() if latest else None,
        })
    return _ok(result, count=len(result))


# ── /api/stock/<symbol> ────────────────────────────────────────────────────────

@api_bp.route('/stock/<symbol>')
def stock_detail(symbol):
    s = Stock.query.filter_by(symbol=symbol.upper()).first()
    if not s:
        return _err(f"Symbol '{symbol}' not found.", 404)

    days  = int(request.args.get('days', 90))
    since = datetime.utcnow() - timedelta(days=days)

    prices = (Price.query
              .filter(Price.stock_id == s.id, Price.datetime >= since)
              .order_by(Price.datetime).all())
    inds   = (Indicator.query
              .filter(Indicator.stock_id == s.id, Indicator.datetime >= since)
              .order_by(Indicator.datetime).all())
    sig    = (Signal.query
              .filter_by(stock_id=s.id)
              .order_by(desc(Signal.datetime)).first())

    return _ok({
        'stock':      s.to_dict(),
        'prices':     [p.to_dict() for p in prices],
        'indicators': [i.to_dict() for i in inds],
        'signal':     sig.to_dict() if sig else None,
    })


# ── /api/stock/<symbol>/history ────────────────────────────────────────────────

@api_bp.route('/stock/<symbol>/history')
def stock_history(symbol):
    s = Stock.query.filter_by(symbol=symbol.upper()).first()
    if not s:
        return _err(f"Symbol '{symbol}' not found.", 404)

    days  = int(request.args.get('days', 90))
    since = datetime.utcnow() - timedelta(days=days)
    prices = (Price.query
              .filter(Price.stock_id == s.id, Price.datetime >= since)
              .order_by(Price.datetime).all())
    return _ok([p.to_dict() for p in prices])


# ── /api/signals ──────────────────────────────────────────────────────────────

@api_bp.route('/signals')
def all_signals():
    """Latest trading signal for every active stock."""
    # Subquery: latest signal datetime per stock
    sub = (db.session.query(Signal.stock_id,
                            func.max(Signal.datetime).label('max_dt'))
           .group_by(Signal.stock_id).subquery())

    rows = (db.session.query(Signal, Stock)
            .join(sub, (Signal.stock_id == sub.c.stock_id) &
                       (Signal.datetime == sub.c.max_dt))
            .join(Stock, Signal.stock_id == Stock.id)
            .filter(Stock.is_active == True)
            .all())

    result = []
    for sig, stk in rows:
        d = sig.to_dict()
        d.update({'symbol': stk.symbol, 'name': stk.name, 'sector': stk.sector})
        result.append(d)

    # Filter by signal type
    stype = request.args.get('type', '').upper()
    if stype in ('BUY', 'SELL', 'HOLD'):
        result = [r for r in result if r['signal'] == stype]

    result.sort(key=lambda x: x.get('confidence', 0), reverse=True)
    return _ok(result, count=len(result))


# ── /api/top-movers ───────────────────────────────────────────────────────────

@api_bp.route('/top-movers')
def top_movers():
    """Return top-5 gainers and top-5 losers by % change."""
    stocks  = Stock.query.filter_by(is_active=True).all()
    movers  = []

    for s in stocks:
        prices = (Price.query
                  .filter_by(stock_id=s.id)
                  .order_by(desc(Price.datetime))
                  .limit(2).all())
        if len(prices) < 2:
            continue
        curr, prev = float(prices[0].close), float(prices[1].close)
        if prev == 0:
            continue
        change_pct = round((curr - prev) / prev * 100, 2)
        movers.append({
            'symbol': s.symbol, 'name': s.name, 'sector': s.sector,
            'close': curr, 'change_pct': change_pct,
            'change': round(curr - prev, 2),
        })

    movers.sort(key=lambda x: x['change_pct'], reverse=True)
    return _ok({
        'gainers': movers[:5],
        'losers':  list(reversed(movers[-5:])),
    })


# ── /api/market-summary ───────────────────────────────────────────────────────

@api_bp.route('/market-summary')
def market_summary():
    total_stocks  = Stock.query.filter_by(is_active=True).count()
    buy_signals   = Signal.query.filter_by(signal_type='BUY').count()
    sell_signals  = Signal.query.filter_by(signal_type='SELL').count()
    hold_signals  = Signal.query.filter_by(signal_type='HOLD').count()
    total_prices  = Price.query.count()

    latest_update = (db.session.query(func.max(Price.datetime)).scalar())

    return _ok({
        'total_stocks':  total_stocks,
        'buy_signals':   buy_signals,
        'sell_signals':  sell_signals,
        'hold_signals':  hold_signals,
        'total_price_records': total_prices,
        'last_updated':  latest_update.isoformat() if latest_update else None,
    })


# ── /api/admin endpoints ──────────────────────────────────────────────────────

@api_bp.route('/admin/seed', methods=['POST'])
def admin_seed():
    try:
        from app.services.data_ingestion import seed_stock_universe
        seed_stock_universe()
        return _ok({'message': 'Stock universe seeded successfully.'})
    except Exception as exc:
        logger.error("Seed error: %s", exc)
        return _err(str(exc), 500)


@api_bp.route('/admin/refresh', methods=['POST'])
def admin_refresh():
    """Trigger a full refresh asynchronously (returns immediately)."""
    import threading
    from app.services.data_ingestion import refresh_all_stocks
    from flask import current_app
    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            refresh_all_stocks(days=365)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return _ok({'message': 'Full refresh started in background.'})


@api_bp.route('/admin/refresh/<symbol>', methods=['POST'])
def admin_refresh_symbol(symbol):
    """Refresh a single stock immediately."""
    from app.services.data_ingestion import refresh_single_stock
    s = Stock.query.filter_by(symbol=symbol.upper()).first()
    if not s:
        return _err(f"Symbol '{symbol}' not found.", 404)
    try:
        refresh_single_stock(s, days=365)
        return _ok({'message': f'{symbol} refreshed.'})
    except Exception as exc:
        logger.error("Refresh error for %s: %s", symbol, exc)
        return _err(str(exc), 500)
