"""
Technical Indicator Engine
Computes SMA, EMA, RSI, MACD, Bollinger Bands and derives BUY/SELL/HOLD signals.
"""
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Pure-pandas indicator calculations ────────────────────────────────────────

def compute_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def compute_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta  = series.diff()
    gain   = delta.clip(lower=0)
    loss   = -delta.clip(upper=0)
    avg_g  = gain.ewm(alpha=1/window, adjust=False, min_periods=window).mean()
    avg_l  = loss.ewm(alpha=1/window, adjust=False, min_periods=window).mean()
    rs     = avg_g / avg_l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast   = compute_ema(series, fast)
    ema_slow   = compute_ema(series, slow)
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger(series: pd.Series, window=20, num_std=2):
    sma    = compute_sma(series, window)
    std    = series.rolling(window=window).std(ddof=0)
    upper  = sma + num_std * std
    lower  = sma - num_std * std
    return upper, sma, lower


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a DataFrame with a 'close' column, append all indicator columns.
    Returns the same DataFrame with new columns added in-place.
    """
    close = df['close'].astype(float)

    df['sma_20']  = compute_sma(close, 20)
    df['sma_50']  = compute_sma(close, 50)
    df['sma_200'] = compute_sma(close, 200)
    df['ema_12']  = compute_ema(close, 12)
    df['ema_26']  = compute_ema(close, 26)
    df['rsi']     = compute_rsi(close, 14)

    macd, macd_sig, macd_hist = compute_macd(close)
    df['macd']        = macd
    df['macd_signal'] = macd_sig
    df['macd_hist']   = macd_hist

    bb_u, bb_m, bb_l = compute_bollinger(close)
    df['bb_upper']  = bb_u
    df['bb_middle'] = bb_m
    df['bb_lower']  = bb_l

    return df


# ── Signal generation ─────────────────────────────────────────────────────────

def generate_signal(row: pd.Series) -> dict:
    """
    Rules-based signal for a single candle row that already has indicators.

    Scoring (each criterion ±1):
      • RSI < 30  → +2 BUY  |  RSI > 70 → -2 SELL
      • MACD > Signal        → +1        |  < → -1
      • Close > SMA-50       → +1        |  < → -1
      • Close > EMA-12       → +1        |  < → -1
      • SMA-20 > SMA-50      → +1 (golden cross area) | vice-versa → -1

    Score ≥ 3  → BUY   (high confidence if ≥ 4)
    Score ≤ -3 → SELL
    else       → HOLD
    """
    reasons = []
    score   = 0

    rsi        = row.get('rsi')
    macd       = row.get('macd')
    macd_sig   = row.get('macd_signal')
    close      = row.get('close')
    sma_20     = row.get('sma_20')
    sma_50     = row.get('sma_50')
    ema_12     = row.get('ema_12')

    # RSI
    if rsi is not None and not np.isnan(rsi):
        if rsi < 30:
            score += 2; reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi < 40:
            score += 1; reasons.append(f"RSI near oversold ({rsi:.1f})")
        elif rsi > 70:
            score -= 2; reasons.append(f"RSI overbought ({rsi:.1f})")
        elif rsi > 60:
            score -= 1; reasons.append(f"RSI near overbought ({rsi:.1f})")

    # MACD
    if macd is not None and macd_sig is not None and not (np.isnan(macd) or np.isnan(macd_sig)):
        if macd > macd_sig:
            score += 1; reasons.append("MACD above signal (bullish)")
        else:
            score -= 1; reasons.append("MACD below signal (bearish)")

    # Price vs SMA-50
    if close and sma_50 and not np.isnan(sma_50):
        if close > sma_50:
            score += 1; reasons.append("Price above SMA-50")
        else:
            score -= 1; reasons.append("Price below SMA-50")

    # Price vs EMA-12
    if close and ema_12 and not np.isnan(ema_12):
        if close > ema_12:
            score += 1; reasons.append("Price above EMA-12")
        else:
            score -= 1; reasons.append("Price below EMA-12")

    # Golden/death cross area
    if sma_20 and sma_50 and not (np.isnan(sma_20) or np.isnan(sma_50)):
        if sma_20 > sma_50:
            score += 1; reasons.append("SMA-20 > SMA-50 (golden zone)")
        else:
            score -= 1; reasons.append("SMA-20 < SMA-50 (death zone)")

    # Determine signal
    if score >= 3:
        signal_type = 'BUY'
        confidence  = min(100, 50 + score * 8)
    elif score <= -3:
        signal_type = 'SELL'
        confidence  = min(100, 50 + abs(score) * 8)
    else:
        signal_type = 'HOLD'
        confidence  = 50.0

    return {
        'signal_type': signal_type,
        'confidence':  round(confidence, 2),
        'reason':      '; '.join(reasons) if reasons else 'Insufficient data',
    }
