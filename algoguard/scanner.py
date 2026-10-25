"""Volatility scanner: find stocks that got calmer while the market (India VIX) got more fearful.

India VIX measures expected volatility of the NIFTY index as a whole, not of each stock, so
when VIX rises some stocks still calm down. This scans for them on any date, using only data
up to that date.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import realized_vol


def scan(prices: dict, vix: pd.Series, day, lookback: int = 10, window: int = 20) -> tuple[pd.DataFrame, float]:
    """Compare each stock's `window`-day volatility on `day` with `lookback` sessions earlier.

    Returns (table sorted calmest-first, VIX change in % over the same lookback)."""
    rows = []
    for sym, df in prices.items():
        v = realized_vol(df["close"], window).loc[:pd.Timestamp(day)].dropna()
        if len(v) <= lookback:
            continue
        now, before = v.iloc[-1] * 100, v.iloc[-1 - lookback] * 100
        rows.append({"Stock": sym.replace(".NS", ""), "Volatility now %": now, "Volatility before %": before,
                     "Change %": (now / before - 1) * 100})
    x = vix.loc[:pd.Timestamp(day)].dropna()
    vix_chg = (x.iloc[-1] / x.iloc[-1 - lookback] - 1) * 100 if len(x) > lookback else np.nan
    tbl = pd.DataFrame(rows).sort_values("Change %").reset_index(drop=True)
    tbl["Calmer while VIX rose"] = (tbl["Change %"] < 0) & (vix_chg > 0)
    return tbl, vix_chg
