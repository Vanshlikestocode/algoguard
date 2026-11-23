"""Weekly top-K portfolio with a drawdown-triggered re-evaluation (never a sell-everything rule).

Timing: scores and regime are known at the close of day t-1; the portfolio is rebalanced at
the open of the first trading day of each week (or the day after a trigger); 0.15% cost per
side on every rupee traded; marked at the close.

Drawdown trigger: when the portfolio is `dd` below its peak, the engine re-evaluates using only
data up to that close: it can retrain the stress model on recent data (retrain_fn), scores every
candidate approach over the last `window` sessions, switches to the best one (by Sharpe), stays
fully invested, logs the reason, and re-arms from the current level after a cooldown.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

CANDIDATES = ["regime_switch", "regime_switch_gb", "momentum", "stress", "low_vol", "equal_weight"]


def policy_scores(policy: str, scores: dict, regime: str | None) -> str:
    """Which score frame a policy uses today."""
    calm = regime in (None, "calm")
    if policy == "regime_switch":
        return "momentum" if calm else "stress"
    if policy == "regime_switch_gb":
        return "momentum" if calm else "stress_gb"
    return policy


def pick(row: pd.Series, vol: pd.Series, k: int, equal: bool = False) -> pd.Series:
    """Top-k by score, inverse-volatility weights summing to 1 (equal=True: every stock, equal weights)."""
    ok = row.dropna().index.intersection(vol.dropna().index)
    if not len(ok):
        return pd.Series(dtype=float)
    if equal:
        return pd.Series(1 / len(ok), index=ok)
    top = row[ok].nlargest(k).index
    w = 1 / vol[top].clip(lower=0.05)
    return w / w.sum()


@dataclass
class Result:
    equity: pd.Series
    exposure: pd.Series
    turnover: pd.Series
    holdings: dict
    log: pd.DataFrame
    active: pd.Series = field(default=None)


def quick_sharpe(policy, scores, regime, C, vol, end_i, window, k, cost) -> float:
    """Sharpe of a policy over the `window` sessions ending at index end_i (close-to-close,
    weekly rebalance, costs). Uses only data up to end_i."""
    idx = C.index
    lo = max(1, end_i - window + 1)
    rets, w_prev = [], pd.Series(dtype=float)
    w = pd.Series(dtype=float)
    for i in range(lo, end_i + 1):
        if i == lo or idx[i].isocalendar()[1] != idx[i - 1].isocalendar()[1]:
            name = policy_scores(policy, scores, regime.iloc[i - 1] if regime is not None else None)
            frame = scores.get(name)
            if frame is None or idx[i - 1] not in frame.index:
                continue
            w = pick(frame.loc[idx[i - 1]], vol.iloc[i - 1], k, name == "equal_weight")
            tc = (w.reindex(w.index.union(w_prev.index), fill_value=0) - w_prev.reindex(w.index.union(w_prev.index), fill_value=0)).abs().sum() * cost
            w_prev = w
        else:
            tc = 0.0
        r = (C.iloc[i][w.index] / C.iloc[i - 1][w.index] - 1).fillna(0)
        rets.append(float((w * r).sum()) - tc)
    rets = np.array(rets)
    if len(rets) < 20 or rets.std() == 0:
        return -np.inf
    return rets.mean() / rets.std() * np.sqrt(252)


def run(O: pd.DataFrame, C: pd.DataFrame, vol: pd.DataFrame, scores: dict, regime: pd.Series | None,
        policy: str = "regime_switch", k: int = 10, cost: float = 0.0015, dd: float | None = None,
        window: int = 126, cooldown: int = 20, retrain_fn=None, capital: float = 1_000_000) -> Result:
    idx = C.index
    Of, Cf = O.ffill(), C.ffill()  # pricing only; trading needs a real open
    shares = pd.Series(0.0, index=C.columns)
    cash = float(capital)
    eq, expo, turn, holdings, log, active_hist = [], [], {}, {}, [], []
    peak, last_trig, active, force = capital, -10**9, policy, False
    for i in range(len(idx)):
        if i > 0 and (force or idx[i].isocalendar()[1] != idx[i - 1].isocalendar()[1]):
            force = False
            name = policy_scores(active, scores, regime.iloc[i - 1] if regime is not None else None)
            frame = scores.get(name)
            if frame is not None and idx[i - 1] in frame.index:
                row = frame.loc[idx[i - 1]].where(O.iloc[i].notna())
                w = pick(row, vol.iloc[i - 1], k, name == "equal_weight")
                eq_open = cash + float((shares * Of.iloc[i]).fillna(0).sum())
                # a holding with no open price today cannot be sold, so it stays as is and only the rest is re-spent
                stuck = float((shares * Of.iloc[i]).where(O.iloc[i].isna(), 0.0).fillna(0).sum())
                target = (w * (eq_open - stuck) * (1 - 2 * cost) / O.iloc[i][w.index]).reindex(C.columns, fill_value=0.0)  # buffer: never leveraged
                tradable = O.iloc[i].notna() | target.gt(0)
                delta = (target - shares).where(tradable, 0.0)
                notional = (delta.abs() * Of.iloc[i]).fillna(0).sum()
                cash -= float((delta * Of.iloc[i]).fillna(0).sum()) + notional * cost
                shares = shares + delta
                turn[idx[i]] = notional / eq_open
                holdings[idx[i]] = {"policy": active, "scores": name, "weights": w.round(4).to_dict()}
        mv = float((shares * Cf.iloc[i]).fillna(0).sum())
        e = cash + mv
        eq.append(e)
        expo.append(mv / e if e > 0 else 0)
        active_hist.append(active)
        peak = max(peak, e)
        if dd is not None and e / peak - 1 <= -dd and i - last_trig >= cooldown:
            note = ""
            if retrain_fn is not None:
                note = retrain_fn(i, scores) or ""
            perf = {c: quick_sharpe(c, scores, regime, C, vol, i, window, k, cost) for c in CANDIDATES}
            best = max(perf, key=perf.get)
            log.append({"date": idx[i], "rule": "drawdown_trigger", "action": "RE-EVALUATE",
                        "detail": f"drawdown {e / peak - 1:.1%} reached -{dd:.0%}; {note}"
                                  f"last {window} sessions Sharpe: " + ", ".join(f"{c} {v:.2f}" for c, v in perf.items())
                                  + f"; switched {active} -> {best}; stayed fully invested"})
            active, peak, last_trig, force = best, e, i, True
    return Result(pd.Series(eq, index=idx), pd.Series(expo, index=idx), pd.Series(turn),
                  holdings, pd.DataFrame(log, columns=["date", "rule", "action", "detail"]), pd.Series(active_hist, index=idx))
