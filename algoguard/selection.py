"""Resilience ranking: which NIFTY 50 stocks beat the index over the next N sessions?

Two models per training window, one per volatility regime:
  "calm" - trained on days when NIFTY's realised volatility over the next N sessions was NOT high
  "high" - trained on days when it WAS high (the stress model)
The regime used for training is the realised one (known for past data); when trading, the
forecast regime decides which model to use: calm -> momentum ranking, rising/high -> stress model.
Features enter as cross-sectional ranks (0..1) so their scale does not matter.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import FEATURES, N

COLS = [f"{c}_r" for c in FEATURES]


def _train_rows(panel: pd.DataFrame, regime_y: pd.Series, start, end):
    """Rows usable for training: target complete before `end`, every 5th date (less overlap)."""
    dates = panel.index.get_level_values("date")
    cal = regime_y.index
    last_ok = cal[cal.get_indexer([pd.Timestamp(end)], method="pad")[0] - N]
    keep = (dates <= last_ok) & (dates >= pd.Timestamp(start) if start is not None else True)
    sample = set(cal[::5])
    keep &= dates.isin(sample)
    p = panel[keep].dropna(subset=COLS + ["y"])
    p = p.assign(reg=regime_y.reindex(p.index.get_level_values("date")).values).dropna(subset=["reg"])
    return p


def fit(panel: pd.DataFrame, regime_y: pd.Series, end, start=None, kind: str = "lr") -> dict:
    """Fit one model per realised regime on data with complete targets before `end`."""
    p = _train_rows(panel, regime_y, start, end)
    models = {}
    for name, mask in (("calm", p["reg"] == 0), ("high", p["reg"] == 1)):
        X, y = p.loc[mask, COLS], p.loc[mask, "y"]
        if len(X) < 500:
            continue
        if kind == "lr":
            m = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000)).fit(X, y)
        else:
            m = HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.05, random_state=0).fit(X, y)
        models[name] = m
    return models


def score(models: dict, panel: pd.DataFrame, name: str, start, end) -> pd.DataFrame:
    """Probability of beating NIFTY, as a dates x tickers frame, for dates in [start, end]."""
    if name not in models:
        return pd.DataFrame()
    d = panel.index.get_level_values("date")
    p = panel[(d >= pd.Timestamp(start)) & (d <= pd.Timestamp(end))].dropna(subset=COLS)
    s = pd.Series(models[name].predict_proba(p[COLS])[:, 1], index=p.index)
    return s.unstack("ticker")


def importance(models: dict) -> pd.DataFrame:
    """Standardised logistic coefficients per regime (positive = helps a stock beat NIFTY)."""
    out = {}
    for name, m in models.items():
        lr = m.named_steps["logisticregression"]
        out[name] = pd.Series(lr.coef_[0], index=FEATURES)
    return pd.DataFrame(out)


def information_coefficient(panel: pd.DataFrame, regime_y: pd.Series, start, end, regime: int) -> pd.Series:
    """Average daily rank correlation between each feature and the next-N excess return, on days
    of the given realised regime. Positive = a higher value went with beating NIFTY."""
    d = panel.index.get_level_values("date")
    p = panel[(d >= pd.Timestamp(start)) & (d <= pd.Timestamp(end))]
    days = regime_y[regime_y == regime].index[::5]
    p = p[p.index.get_level_values("date").isin(days)].dropna(subset=["fwd_excess"])
    fe = p.groupby(level="date")["fwd_excess"].rank(pct=True)
    return pd.Series({c: p[f"{c}_r"].corr(fe) for c in FEATURES})
