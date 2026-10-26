"""Volatility regime forecast for NIFTY 50.

Target: is NIFTY's realised volatility over the NEXT `H` sessions "high", i.e. above the
75th percentile of 10-day realised volatility over the trailing year (a threshold known at t)?
Inputs known at the close of day t: India VIX level and 5-day change, realised volatility
(10 and 20 day), the VIX / realised-vol ratio, and a GARCH(1,1) one-day-ahead volatility whose
parameters are fitted only on data before the forecast year. VIX futures term structure is not
freely available, so it is not used.

Regime from the probability p of high volatility (thresholds fixed before testing):
  calm p < 0.30, rising 0.30 <= p < 0.50, high p >= 0.50.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

H = 10  # forecast horizon in sessions
FEATURES = ["vix", "vix_chg5", "rv10", "rv20", "garch", "vix_rv"]
LEVELS = [(0.50, "high"), (0.30, "rising"), (0.0, "calm")]


def _rv(r: pd.Series, n: int) -> pd.Series:
    return r.rolling(n, min_periods=n).std() * np.sqrt(252) * 100


def garch_vol(r: pd.Series, fit_end: pd.Timestamp) -> pd.Series:
    """One-day-ahead GARCH(1,1) volatility (annualised %) for every day, with parameters fitted
    on returns up to `fit_end` only. sigma_{t+1} uses returns up to t, so no look-ahead."""
    from arch import arch_model
    x = r.dropna() * 100
    fit = arch_model(x.loc[:fit_end], mean="Constant", vol="GARCH", p=1, q=1, rescale=False).fit(disp="off")
    mu, om, a, b = (fit.params[k] for k in ("mu", "omega", "alpha[1]", "beta[1]"))
    eps = (x - mu).values
    var = np.empty(len(x))
    var[0] = eps[: min(250, len(eps))].var()
    for t in range(1, len(x)):
        var[t] = om + a * eps[t - 1] ** 2 + b * var[t - 1]
    nxt = om + a * eps ** 2 + b * var  # variance for t+1, known at the close of t
    return pd.Series(np.sqrt(nxt * 252), index=x.index).reindex(r.index)


def base_frame(nifty_close: pd.Series, vix: pd.Series) -> pd.DataFrame:
    """Features that need no fitting, plus the target. Index = NIFTY trading days."""
    r = np.log(nifty_close).diff()
    v = vix.reindex(nifty_close.index).ffill()
    f = pd.DataFrame(index=nifty_close.index)
    f["vix"], f["vix_chg5"] = v, np.log(v).diff(5) * 100
    f["rv10"], f["rv20"] = _rv(r, 10), _rv(r, 20)
    f["vix_rv"] = f["vix"] / f["rv20"]
    f["thr"] = f["rv10"].rolling(252, min_periods=126).quantile(0.75)  # known at t
    fwd = r[::-1].rolling(H, min_periods=H).std()[::-1].shift(-1) * np.sqrt(252) * 100  # days t+1..t+H
    f["fwd_rv"] = fwd
    f["y"] = (fwd > f["thr"]).astype(float).where(fwd.notna() & f["thr"].notna())
    f["naive"] = (f["rv10"] > f["thr"]).astype(float)  # "the next H days look like the last 10"
    f["ret"] = r
    return f


def label(p: float) -> str:
    return next(name for cut, name in LEVELS if p >= cut)


def walk_forward(nifty_close: pd.Series, vix: pd.Series, first_year: int) -> pd.DataFrame:
    """Every 1 January refit GARCH and the logistic model on data before it, then forecast that
    year. Returns the base frame with columns garch, p_high and regime (NaN before first_year)."""
    f = base_frame(nifty_close, vix)
    f["garch"], f["p_high"], f["regime"] = np.nan, np.nan, None
    for year in range(first_year, f.index[-1].year + 1):
        start = pd.Timestamp(f"{year}-01-01")
        cut = f.index[f.index < start]
        if len(cut) <= H + 300:
            continue
        g = garch_vol(f["ret"], cut[-1])
        X = f[FEATURES[:-2] + ["vix_rv"]].assign(garch=g)[FEATURES]
        # train only on rows whose H-day future is complete before the year starts
        train = X.index.isin(cut[:-H]) & X.notna().all(axis=1) & f["y"].notna()
        model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(X[train], f.loc[train, "y"])
        yr = (X.index >= start) & (X.index.year == year) & X.notna().all(axis=1)
        f.loc[yr, "garch"] = g[yr]
        f.loc[yr, "p_high"] = model.predict_proba(X[yr])[:, 1]
    f.loc[f["p_high"].notna(), "regime"] = f.loc[f["p_high"].notna(), "p_high"].map(label)
    return f


def accuracy(f: pd.DataFrame, start=None, end=None) -> dict:
    """Hit rate and confusion matrix of the forecast (p >= 0.5 means 'high') vs the naive
    persistence baseline, on days with a known outcome."""
    d = f.loc[start:end].dropna(subset=["p_high", "y"])
    pred, naive, y = (d["p_high"] >= 0.5).astype(int), d["naive"].astype(int), d["y"].astype(int)
    cm = pd.crosstab(y.rename("actual"), pred.rename("forecast")).reindex(index=[0, 1], columns=[0, 1], fill_value=0)
    tp, fp, fn = cm.loc[1, 1], cm.loc[0, 1], cm.loc[1, 0]
    return {"days": len(d), "share_high": y.mean(), "hit_rate": (pred == y).mean(), "naive_hit_rate": (naive == y).mean(),
            "precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1),
            "naive_recall": ((naive == 1) & (y == 1)).sum() / max(y.sum(), 1), "confusion": cm}
