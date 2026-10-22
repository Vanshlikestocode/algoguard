"""Guarded v2: strategy-aware guardrails, chosen on in-sample data only.

v1 applied one generic rule set to every strategy. The ablation showed that some rules
hurt some strategies (the drawdown breaker's forced sell-off on EMA, ATR stops on Donchian
and RSI-2). v2 lets each strategy pick its own setting for the three rules in question,
from a small fixed menu, and leaves every other rule as in v1.

Honesty protocol:
  1. The menu and the selection rule are fixed in this file before any test is run.
  2. Every candidate is backtested on data BEFORE the split date only (the data is cut,
     not just the scoring window, so nothing after the split can leak in).
  3. The winner per strategy is the highest in-sample Calmar (CAGR / |max drawdown|).
     Ties go to the candidate closest to v1.
  4. The chosen settings are then run once on the out-of-sample period and reported as is.
"""
from __future__ import annotations

from dataclasses import replace
from itertools import product

import pandas as pd

from .backtest import run_backtest
from .metrics import summarize
from .risk import GUARDED, RiskConfig

# The menu: 2 x 2 x 4 = 16 candidates per strategy. Small on purpose: the more settings
# you try, the more likely the winner is luck.
MENU = {
    "dd_flatten": [True, False],              # breaker sells everything, or only blocks entries
    "vix_limit": [GUARDED.vix_limit, None],   # VIX filter on or off
    "stop_atr_mult": [3.0, 4.0, 5.0, None],   # stop distance, or no stop (rely on the exit signal)
}


def candidates() -> list[RiskConfig]:
    keys = list(MENU)
    return [replace(GUARDED, **dict(zip(keys, vals))) for vals in product(*MENU.values())]


def _changes_from_v1(cfg: RiskConfig) -> int:
    return sum(getattr(cfg, k) != getattr(GUARDED, k) for k in MENU)


def describe(cfg: RiskConfig) -> str:
    parts = ["breaker: " + ("sell all" if cfg.dd_flatten else "block entries only"),
             "VIX filter: " + ("on" if cfg.vix_limit is not None else "off"),
             "stop: " + (f"{cfg.stop_atr_mult:g}x ATR" if cfg.stop_atr_mult is not None else "none")]
    return ", ".join(parts)


def select(prices: dict, signals: pd.DataFrame, vix: pd.Series | None, split: pd.Timestamp):
    """Return (chosen config, table of every candidate's in-sample score)."""
    end = split - pd.Timedelta(days=1)
    p_in = {s: df.loc[:end] for s, df in prices.items()}
    sig_in = signals.loc[:end]
    vix_in = vix.loc[:end] if vix is not None else None
    rows = []
    for cfg in candidates():
        m = summarize(run_backtest(p_in, sig_in, vix_in, cfg).equity)
        rows.append({"config": cfg, "Setting": describe(cfg), "Changes vs v1": _changes_from_v1(cfg),
                     "IS CAGR %": m["CAGR %"], "IS Max DD %": m["Max drawdown %"], "IS Calmar": m["Calmar"]})
    tbl = pd.DataFrame(rows).sort_values(["IS Calmar", "Changes vs v1"], ascending=[False, True])
    return tbl.iloc[0]["config"], tbl.drop(columns="config").reset_index(drop=True)


def walk_forward(prices: dict, signals: pd.DataFrame, vix: pd.Series | None, first_year: int, last_year: int):
    """Re-pick the v2 setting every 1 January using only data before it, trade that year with it,
    and stitch the years into one curve. Every year is out-of-sample for the setting it uses.

    Returns (equity curve starting at 1.0, table of the setting chosen each year)."""
    rets, picks = [], []
    for year in range(first_year, last_year + 1):
        start, end = pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-12-31")
        cfg, _ = select(prices, signals, vix, start)
        # the engine keeps running across years; only the settings switch on 1 January
        eq = run_backtest(prices, signals, vix, cfg).equity
        rets.append(eq.pct_change().loc[start:end])
        picks.append({"Year": year, "Setting chosen on data before it": describe(cfg)})
    r = pd.concat(rets).fillna(0)
    return (1 + r).cumprod(), pd.DataFrame(picks)
