"""Explain one trading day in plain English, from a backtest Result: what was bought or sold,
and which guardrail stepped in and why. Built for people who do not trade."""
from __future__ import annotations

import pandas as pd

WHY_BLOCKED = {
    "vix_limit": "the market's fear meter (India VIX) was above {vix:g}",
    "daily_loss_limit": "a cooldown after a bad day was still on",
    "consec_loss_limit": "a pause after a losing streak was still on",
    "max_drawdown": "the circuit breaker had stopped new buying",
}
WHY_SOLD = {
    "signal": "the strategy's sell signal came",
    "risk: ATR stop": "the stop-loss was hit",
    "risk: flatten": "the circuit breaker sold everything",
}


def _names(syms) -> str:
    syms = [s.replace(".NS", "") for s in syms]
    return ", ".join(syms[:-1]) + " and " + syms[-1] if len(syms) > 1 else syms[0]


def explain_day(result, day, vix: pd.Series | None = None) -> list[str]:
    """Plain sentences for `day` (any date; a non-trading day uses the trading day before it)."""
    cfg, eq = result.config, result.equity
    day = pd.Timestamp(day)
    i = eq.index.searchsorted(day, side="right") - 1
    if i < 0:
        return ["There is no data before that date."]
    d = eq.index[i]
    out = [] if d == day else [f"Markets were closed on {day:%d %b %Y}, so this is {d:%d %b %Y}."]
    ret = eq.iloc[i] / eq.iloc[i - 1] - 1 if i > 0 else 0.0
    out.append(f"The portfolio was worth Rs {eq.iloc[i]:,.0f}, {'up' if ret >= 0 else 'down'} {abs(ret):.2%} on the day.")

    n_before = len(out)
    tr = result.trades
    if len(tr):
        bought = tr[tr.entry_date == d].symbol.tolist()
        if bought:
            out.append(f"Bought {_names(bought)}.")
        sold = tr[(tr.exit_date == d) & (tr.exit_reason != "end of test")]
        for reason, g in sold.groupby("exit_reason"):
            out.append(f"Sold {_names(g.symbol.tolist())} because {WHY_SOLD.get(reason, reason)}.")

    ev = result.events[result.events.date == d]
    blocked = ev[ev.action == "BLOCKED ENTRY"]
    for rule, g in blocked.groupby("rule"):
        why = WHY_BLOCKED.get(rule, rule).format(vix=cfg.vix_limit or 0)
        out.append(f"Wanted to buy {_names(g.detail.tolist())}, but {why}.")
    for a in ev.action:
        if a == "COOLDOWN":
            out.append(f"That loss is more than the {cfg.daily_loss_limit:.2%} daily limit, so no new buying for "
                       f"the next {cfg.daily_loss_cooldown} trading days.".replace(".00%", "%"))
        elif a == "PAUSE":
            out.append(f"That made {cfg.consec_loss_limit} losing trades in a row, so buying pauses for "
                       f"{cfg.consec_loss_cooldown} trading days.")
        elif a in ("HALT + FLATTEN", "HALT"):
            what = ("everything is sold at the next open and trading stops" if a == "HALT + FLATTEN"
                    else "new buying stops")
            out.append(f"The portfolio fell {cfg.max_drawdown:.0%} or more from its peak, so the circuit breaker "
                       f"tripped: {what} for {cfg.dd_halt_days} trading days.")
        elif a == "RE-ARMED":
            out.append("The circuit breaker's pause is over, so trading starts again.")
    if len(out) == n_before:
        out.append("A quiet day: nothing was bought or sold and no rule stepped in.")
    if vix is not None and d in vix.index and vix.loc[d] == vix.loc[d]:
        out.append(f"India VIX (the market's fear meter) closed at {vix.loc[d]:.1f}.")
    return out
