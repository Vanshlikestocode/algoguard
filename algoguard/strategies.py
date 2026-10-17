"""Signal generators. Each returns a 0/1 target-position Series computed from data up to
and including the close of day t. The backtester acts on it at the OPEN of day t+1, so
there is no look-ahead.

Long-only by design: Indian cash-segment equities cannot be shorted overnight.
"""
from __future__ import annotations

import pandas as pd

from .indicators import ema, rsi, sma


def ema_crossover(df: pd.DataFrame, fast: int = 20, slow: int = 100) -> pd.Series:
    """Trend following: long while fast EMA is above slow EMA."""
    f, s = ema(df["close"], fast), ema(df["close"], slow)
    return (f > s).astype(int).where(s.notna(), 0)


def donchian_breakout(df: pd.DataFrame, entry: int = 55, exit: int = 20) -> pd.Series:
    """Turtle-style: enter on a new `entry`-day high, exit on a new `exit`-day low."""
    hi = df["high"].rolling(entry, min_periods=entry).max().shift(1)
    lo = df["low"].rolling(exit, min_periods=exit).min().shift(1)
    pos, out = 0, []
    for c, h, l in zip(df["close"].values, hi.values, lo.values):
        if pos == 0 and h == h and c > h:
            pos = 1
        elif pos == 1 and l == l and c < l:
            pos = 0
        out.append(pos)
    return pd.Series(out, index=df.index)


def rsi2_mean_reversion(df: pd.DataFrame, entry: float = 10, exit: float = 70, trend: int = 200) -> pd.Series:
    """Connors-style: buy short-term oversold dips in an uptrend, sell on the bounce."""
    r = rsi(df["close"], 2)
    up = df["close"] > sma(df["close"], trend)
    pos, out = 0, []
    for rv, u in zip(r.values, up.values):
        if pos == 0 and u and rv < entry:
            pos = 1
        elif pos == 1 and (rv > exit or not u):
            pos = 0
        out.append(pos)
    return pd.Series(out, index=df.index)


STRATEGIES = {
    "EMA Crossover (20/100)": ema_crossover,
    "Donchian Breakout (55/20)": donchian_breakout,
    "RSI-2 Mean Reversion": rsi2_mean_reversion,
}


def build_signals(prices: dict, fn, **params) -> pd.DataFrame:
    return pd.DataFrame({sym: fn(df, **params) for sym, df in prices.items()})
