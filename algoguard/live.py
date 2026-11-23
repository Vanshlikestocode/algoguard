"""Live market mode: a forward paper-trading record and the plan for the next open, run on fresh data
that is kept apart from the frozen research data (data/ and results/ are never touched, so verify.py
stays exact).

The record starts at the close of START. Each trading day after the NSE close (GitHub Actions runs
`python live_update.py` at 18:00 IST), the same engine as the backtests is re-run from START on the
latest prices, and every new day is appended to live/ledger.csv. Rows already written are never
changed, and each day is a git commit, so the record cannot be edited after the fact.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pandas as pd

from .backtest import run_backtest
from .explain import WHY_BLOCKED
from .risk import GUARDED, PROFILES
from .strategies import STRATEGIES, build_signals

ROOT = Path(__file__).resolve().parent.parent
LIVE = Path(os.environ.get("ALGOGUARD_LIVE", ROOT / "live"))
LIVE_DATA = LIVE / "data"  # downloaded prices; not committed
START = pd.Timestamp(os.environ.get("ALGOGUARD_LIVE_START", "2026-11-23"))  # fixed when the record began
IST = timezone(timedelta(hours=5, minutes=30))
BAR_FINAL = time(16, 30)  # NSE closes 15:30 IST; today's daily bar is treated as final an hour later

SHORT = {"EMA Crossover (20/100)": "EMA", "Donchian Breakout (55/20)": "Donchian", "RSI-2 Mean Reversion": "RSI-2"}
PORTFOLIOS = {f"{SHORT[s]} · {p}": (s, cfg) for s in STRATEGIES
              for p, cfg in (("Balanced (v1)", GUARDED), ("Conservative", PROFILES["Conservative"]))}


def drop_unfinished(prices: dict, vix: pd.Series | None, index: pd.DataFrame | None, now: datetime | None = None):
    """Before 16:30 IST today's bar is still moving: decisions use completed days only."""
    now = now or datetime.now(IST)
    if now.time() >= BAR_FINAL:
        return prices, vix, index
    today = pd.Timestamp(now.date())
    cut = lambda x: None if x is None else x[x.index < today]
    return {k: cut(v) for k, v in prices.items()}, cut(vix), cut(index)


def forward(prices: dict, vix: pd.Series | None, strategy: str, cfg):
    """Run the engine with the strategy flat until START: the first decisions are taken at the close of
    START and filled at the next open, exactly as in the backtests."""
    sig = build_signals(prices, STRATEGIES[strategy])
    sig.loc[sig.index < START] = 0
    return sig, run_backtest(prices, sig, vix, cfg)


def _names(syms) -> str:
    return ", ".join(s.replace(".NS", "") for s in syms)


def day_rows(name: str, sig: pd.DataFrame, res, vix: pd.Series | None, index: pd.DataFrame | None) -> pd.DataFrame:
    """One row per trading day from START: what was filled at the open, what is held at the close,
    what the rules blocked, and the portfolio value."""
    eq, tr, ev = res.equity, res.trades, res.events
    rows = []
    for d in eq.index[eq.index >= START]:
        i = eq.index.get_loc(d)
        if len(tr):
            bought = tr[tr.entry_date == d]
            sold = tr[(tr.exit_date == d) & (tr.exit_reason != "end of test")]
            held = tr[(tr.entry_date <= d) & ((tr.exit_date > d) | (tr.exit_reason == "end of test"))]
        else:
            bought = sold = held = tr
        e = ev[ev.date == d]
        blocked = e[e.action == "BLOCKED ENTRY"].groupby("rule").detail.apply(_names)
        rows.append({
            "date": d.date().isoformat(), "portfolio": name,
            "value_rs": round(float(eq.iloc[i]), 2),
            "day_return_pct": round(float(eq.iloc[i] / eq.iloc[i - 1] - 1) * 100, 4) if i else 0.0,
            "invested_pct": round(float(res.exposure.iloc[i]) * 100, 2),
            "bought_at_open": "; ".join(f"{s.replace('.NS', '')} @ {p:.2f}" for s, p in zip(bought.symbol, bought.entry)),
            "sold": "; ".join(f"{s.replace('.NS', '')} @ {p:.2f} ({r})" for s, p, r in zip(sold.symbol, sold.exit, sold.exit_reason)),
            "holding_at_close": _names(held.symbol),
            "entries_blocked": "; ".join(f"{r}: {s}" for r, s in blocked.items()),
            "risk_events": "; ".join(e[e.action != "BLOCKED ENTRY"].detail),
            "nifty_close": round(float(index["close"].get(d, float("nan"))), 2) if index is not None else None,
            "india_vix": round(float(vix.get(d, float("nan"))), 2) if vix is not None else None,
        })
    return pd.DataFrame(rows)


def plan_next_open(name: str, sig: pd.DataFrame, res, vix: pd.Series | None) -> list[dict]:
    """What the engine will do at the next open, from the state after the last completed close."""
    f, cfg = res.final, res.config
    risk, n = f["risk"], f["n"]
    vix_last = None if vix is None else vix.reindex(sig.index).iloc[-1]
    flatten, block = risk.must_flatten(n), risk.entry_block_reason(n, vix_last)
    out = []
    for s in sig.columns:
        held, want = f["qty"][s] > 0, sig[s].iloc[-1] == 1
        row = {"portfolio": name, "stock": s.replace(".NS", ""), "signal": "long" if want else "flat"}
        if held and (flatten or not want):
            row |= {"action": "SELL", "why": "the drawdown breaker sells everything" if flatten else "the strategy's sell signal came"}
        elif held:
            stop = f["stop"][s]
            row |= {"action": "HOLD", "why": f"stop-loss at {stop:.2f}" if stop == stop else "no stop for this profile"}
        elif want and not flatten:
            if f["stopped_out"][s]:
                row |= {"action": "WAIT", "why": "stopped out earlier; waits for the signal to reset"}
            elif block:
                row |= {"action": "BLOCKED", "why": WHY_BLOCKED.get(block, block).format(vix=cfg.vix_limit or 0)}
            else:
                row |= {"action": "BUY", "why": "the strategy's buy signal came"}
        else:
            continue
        out.append(row)
    return out


def append_ledger(new: pd.DataFrame, path: Path | None = None) -> tuple[int, float]:
    """Add only (date, portfolio) rows that are not in the ledger yet; never rewrite old rows.
    Returns (rows added, largest difference between a stored value and today's recomputation)."""
    path = Path(path or LIVE / "ledger.csv")
    if path.exists():
        old = pd.read_csv(path, dtype=str, keep_default_na=False)
        have = set(zip(old.date, old.portfolio))
        mask = [(d, p) not in have for d, p in zip(new.date, new.portfolio)]
        both = new[[not x for x in mask]].merge(old[["date", "portfolio", "value_rs"]], on=["date", "portfolio"], suffixes=("", "_old"))
        drift = float((both.value_rs.astype(float) - both.value_rs_old.astype(float)).abs().max()) if len(both) else 0.0
        add = new[mask]
        out = pd.concat([old, add.astype(str)], ignore_index=True)
    else:
        add, drift, out = new, 0.0, new
    path.parent.mkdir(parents=True, exist_ok=True)
    out.sort_values(["date", "portfolio"], kind="stable").to_csv(path, index=False)
    return len(add), drift


def volselect_snapshot(folder: Path, now: datetime | None = None) -> tuple[pd.DataFrame, dict]:
    """Today's volatility regime and stock ranking, with the models fitted exactly as in run_vs.py
    (regime and stock models refitted on data up to the previous 31 December)."""
    from . import features, regime, selection, universe
    prices, nifty, vix = universe.load(folder)
    prices, vix, nifty = drop_unfinished(prices, vix, nifty, now)
    nc = nifty["close"]
    last = nc.index[-1]
    f = regime.walk_forward(nc, vix, last.year)
    P = features.panel(prices, nc, f["rv10"] > f["thr"], universe.constituents())
    models = selection.fit(P, f["y"], pd.Timestamp(f"{last.year - 1}-12-31"))
    cur = P.xs(last, level="date").dropna(subset=selection.COLS)
    sectors = universe.constituents().set_index("ticker")["Industry"]
    rank = pd.DataFrame({"stock": [t.replace(".NS", "") for t in cur.index], "sector": sectors.reindex(cur.index).values,
                         "stress_score": models["high"].predict_proba(cur[selection.COLS])[:, 1],
                         "momentum_120d_pct": cur["mom_120"].values * 100, "volatility_20d_pct": cur["vol_20"].values * 100,
                         "beta": cur["beta"].values})
    reg = f["regime"].iloc[-1]
    by = "momentum_120d_pct" if reg in (None, "calm") else "stress_score"  # the regime switch: calm -> momentum
    rank = rank.sort_values(by, ascending=False).reset_index(drop=True)
    rank.insert(0, "rank", range(1, len(rank) + 1))
    rank["in_top_10"] = rank["rank"] <= 10
    state = {"date": last.date().isoformat(), "p_high": round(float(f["p_high"].iloc[-1]), 4), "regime": reg,
             "ranked_by": "120-day momentum (calm market)" if by == "momentum_120d_pct" else "resilience model (rising/high volatility)",
             "india_vix": round(float(f["vix"].iloc[-1]), 2), "nifty_realised_vol_20d": round(float(f["rv20"].iloc[-1]), 2)}
    return rank, state


def write_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8")
