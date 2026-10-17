"""Daily, event-driven portfolio backtester.

Timing (no look-ahead):
  close of day t-1 : signals and risk state are computed
  open of day t    : orders fill at the open price (plus costs)
  during day t     : protective stops can fill (at the stop, or at the open if it gapped through)
  close of day t   : mark to market, risk state updated

Costs per side (default 0.15% of notional): STT on delivery 0.1%, exchange/SEBI/GST/stamp
~0.02%, plus ~0.03% slippage. Zero brokerage assumed (discount broker, delivery).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .indicators import atr, realized_vol
from .risk import RiskConfig, RiskManager


@dataclass
class Result:
    equity: pd.Series
    trades: pd.DataFrame
    events: pd.DataFrame
    blocked: dict
    exposure: pd.Series
    config: RiskConfig


def run_backtest(prices: dict, signals: pd.DataFrame, vix: pd.Series | None, cfg: RiskConfig,
                 capital: float = 1_000_000, cost_rate: float = 0.0015) -> Result:
    syms = list(prices)
    dates = signals.index
    m, n = len(syms), len(dates)
    O = np.column_stack([prices[s]["open"].reindex(dates).values for s in syms])
    H = np.column_stack([prices[s]["high"].reindex(dates).values for s in syms])
    L = np.column_stack([prices[s]["low"].reindex(dates).values for s in syms])
    C = np.column_stack([prices[s]["close"].reindex(dates).values for s in syms])
    A = np.column_stack([atr(prices[s]).reindex(dates).values for s in syms])
    V = np.column_stack([realized_vol(prices[s]["close"]).reindex(dates).values for s in syms])
    S = signals[syms].fillna(0).values.astype(int)
    X = vix.reindex(dates).values if vix is not None else np.full(n, np.nan)

    risk = RiskManager(cfg, dates)
    cash = float(capital)
    qty = np.zeros(m)
    entry_px = np.zeros(m)
    entry_cost = np.zeros(m)
    entry_date = [None] * m
    stop = np.full(m, np.nan)
    equity = np.empty(n)
    expo = np.zeros(n)
    equity[0] = capital
    trades = []

    def close_pos(j, px, t, reason):
        nonlocal cash
        notional = qty[j] * px
        cost = notional * cost_rate
        cash += notional - cost
        pnl = (px - entry_px[j]) * qty[j] - entry_cost[j] - cost
        trades.append({"symbol": syms[j], "entry_date": entry_date[j], "exit_date": dates[t],
                       "qty": int(qty[j]), "entry": entry_px[j], "exit": px, "pnl": pnl,
                       "ret": pnl / (entry_px[j] * qty[j]), "exit_reason": reason})
        qty[j] = 0
        stop[j] = np.nan
        return pnl

    for t in range(1, n):
        closed = []
        flatten = risk.must_flatten(t)
        block = risk.entry_block_reason(t, X[t - 1])
        eq_open = cash + np.nansum(qty * O[t])

        # 1) exits at the open
        for j in range(m):
            if qty[j] > 0 and (S[t - 1, j] == 0 or flatten):
                closed.append(close_pos(j, O[t, j], t, "risk: flatten" if flatten else "signal"))
        # 2) entries at the open
        for j in range(m):
            if qty[j] > 0 or S[t - 1, j] != 1 or flatten or np.isnan(O[t, j]):
                continue
            if block:
                risk.record_block(t, block, syms[j])
                continue
            w = 1.0 / m
            if cfg.vol_target is not None and V[t - 1, j] == V[t - 1, j] and V[t - 1, j] > 0:
                w *= min(1.5, cfg.vol_target / V[t - 1, j])
            w = min(w, cfg.max_position_pct)
            budget = min(w * eq_open, cash / (1 + cost_rate))
            q = np.floor(budget / O[t, j])
            if q <= 0:
                continue
            cost = q * O[t, j] * cost_rate
            cash -= q * O[t, j] + cost
            qty[j], entry_px[j], entry_cost[j], entry_date[j] = q, O[t, j], cost, dates[t]
            if cfg.enabled and cfg.stop_atr_mult is not None and A[t - 1, j] == A[t - 1, j]:
                stop[j] = O[t, j] - cfg.stop_atr_mult * A[t - 1, j]
        # 3) protective stops during the day
        for j in range(m):
            if qty[j] > 0 and stop[j] == stop[j] and L[t, j] <= stop[j]:
                fill = min(O[t, j], stop[j])
                closed.append(close_pos(j, fill, t, "risk: ATR stop"))
        # 4) mark to market at the close
        mv = np.nansum(qty * C[t])
        equity[t] = cash + mv
        expo[t] = mv / equity[t] if equity[t] > 0 else 0
        risk.on_close(t, equity[t], equity[t] / equity[t - 1] - 1, closed)

    # close anything still open at the last close, for trade statistics only
    for j in range(m):
        if qty[j] > 0:
            close_pos(j, C[n - 1, j], n - 1, "end of test")

    return Result(
        equity=pd.Series(equity, index=dates, name="equity"),
        trades=pd.DataFrame(trades),
        events=pd.DataFrame(risk.events, columns=["date", "rule", "action", "detail"]),
        blocked=risk.blocked,
        exposure=pd.Series(expo, index=dates, name="exposure"),
        config=cfg,
    )
