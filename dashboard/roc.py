from typing import Optional

import numpy as np
import pandas as pd


def pct_change(series: pd.Series, periods: int) -> Optional[float]:
    s = series.dropna()
    if len(s) <= periods:
        return None
    return float(s.iloc[-1] / s.iloc[-1 - periods] - 1.0)


def diff(series: pd.Series, periods: int) -> Optional[float]:
    s = series.dropna()
    if len(s) <= periods:
        return None
    return float(s.iloc[-1] - s.iloc[-1 - periods])


def trend_slope(series: pd.Series, lookback: int) -> Optional[float]:
    s = series.dropna().tail(lookback)
    if len(s) < 3:
        return None
    x = np.arange(len(s), dtype=float)
    y = s.values.astype(float)
    slope = np.polyfit(x, y, 1)[0]
    return float(slope)


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    roll_up = up.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    roll_dn = down.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    rs = roll_up / roll_dn.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def higher_highs_higher_lows(series: pd.Series, lookback: int = 20, pivots: int = 3) -> bool:
    """Detect HH+HL pattern in last `lookback` bars using rolling pivots."""
    s = series.dropna().tail(lookback)
    if len(s) < pivots * 2 + 2:
        return False
    window = max(2, lookback // (pivots * 2))
    highs, lows = [], []
    vals = s.values
    for i in range(window, len(vals) - window):
        seg = vals[i - window:i + window + 1]
        if vals[i] == seg.max():
            highs.append((i, vals[i]))
        if vals[i] == seg.min():
            lows.append((i, vals[i]))
    if len(highs) < 2 or len(lows) < 2:
        return False
    hh = all(highs[k][1] > highs[k - 1][1] for k in range(1, len(highs)))
    hl = all(lows[k][1] > lows[k - 1][1] for k in range(1, len(lows)))
    return hh and hl


def relative_strength(stock: pd.Series, benchmark: pd.Series, lookback: int = 63) -> Optional[float]:
    s = stock.dropna().tail(lookback)
    b = benchmark.dropna().tail(lookback)
    if len(s) < lookback or len(b) < lookback:
        return None
    return float((s.iloc[-1] / s.iloc[0]) / (b.iloc[-1] / b.iloc[0]) - 1.0)
