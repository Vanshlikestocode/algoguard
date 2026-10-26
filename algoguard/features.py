"""Per-stock features for the resilience ranking. Every feature on day t uses data up to the
close of t only; the target (`fwd_excess`, `y`) is the future and is used only for training."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import adx, atr, bollinger_pctb, macd_hist, obv, rsi, sma, stoch_k

N = 10  # target horizon: does the stock beat NIFTY over the next N sessions?
FEATURES = ["beta", "down_beta", "hv_excess", "defensive", "rel_strength", "liquidity", "rsi", "macd", "adx",
            "pct_b", "atr_pct", "obv_trend", "stoch", "ma50_dist", "ma200_dist", "mom_20", "mom_60", "mom_120", "vol_20"]


def stock_features(df: pd.DataFrame, nifty_close: pd.Series, high_vol_day: pd.Series, defensive: bool) -> pd.DataFrame:
    idx = nifty_close.index
    c = df["close"].reindex(idx)
    r, m = c.pct_change(fill_method=None), nifty_close.pct_change()
    f = pd.DataFrame(index=idx)
    cov = r.rolling(120, min_periods=60).cov(m)
    f["beta"] = cov / m.rolling(120, min_periods=60).var()
    md = m.where(m < 0)
    f["down_beta"] = r.where(m < 0).rolling(120, min_periods=30).cov(md) / md.rolling(120, min_periods=30).var()
    ex = r - m
    hv = high_vol_day.reindex(idx).fillna(False).astype(float)
    f["hv_excess"] = (ex * hv).rolling(504, min_periods=60).sum() / hv.rolling(504, min_periods=60).sum().where(lambda x: x >= 20)
    f["defensive"] = float(defensive)
    f["rel_strength"] = c.pct_change(60, fill_method=None) - nifty_close.pct_change(60)
    f["liquidity"] = np.log((df["close"] * df["volume"]).rolling(20, min_periods=20).mean().reindex(idx))
    d = df.reindex(idx)
    f["rsi"] = rsi(c, 14).where(c.rolling(15).count() == 15)  # rsi() fills its warm-up with 100
    f["macd"] = macd_hist(c) / c
    f["adx"] = adx(df).reindex(idx)
    f["pct_b"] = bollinger_pctb(c)
    f["atr_pct"] = atr(df).reindex(idx) / c
    o = obv(df).reindex(idx)
    f["obv_trend"] = (o - o.shift(20)) / (d["volume"].rolling(20, min_periods=20).mean() * 20)
    f["stoch"] = stoch_k(df).reindex(idx)
    f["ma50_dist"], f["ma200_dist"] = c / sma(c, 50) - 1, c / sma(c, 200) - 1
    for n in (20, 60, 120):
        f[f"mom_{n}"] = c.pct_change(n, fill_method=None)
    f["vol_20"] = r.rolling(20, min_periods=20).std() * np.sqrt(252)
    f["fwd_excess"] = c.shift(-N) / c - nifty_close.shift(-N) / nifty_close
    f["listed"] = c.notna()
    return f


def panel(prices: dict, nifty_close: pd.Series, high_vol_day: pd.Series, sectors: pd.DataFrame) -> pd.DataFrame:
    """Long frame indexed by (date, ticker), with raw features, cross-sectional ranks (*_r, 0..1)
    and the target y = 1 if the stock beat NIFTY over the next N sessions."""
    defensive = dict(zip(sectors.ticker, sectors.defensive))
    frames = {t: stock_features(df, nifty_close, high_vol_day, defensive.get(t, False)) for t, df in prices.items()}
    p = pd.concat(frames, names=["ticker", "date"]).swaplevel().sort_index()
    p = p[p["listed"]]
    ranks = p[FEATURES].groupby(level="date").rank(pct=True)
    ranks["defensive"] = p["defensive"]  # already 0/1
    p[[f"{c}_r" for c in FEATURES]] = ranks.values
    p["y"] = (p["fwd_excess"] > 0).astype(float).where(p["fwd_excess"].notna())
    return p
