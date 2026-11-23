"""Live mode: flat before the record starts, append-only ledger, a correct plan for the next open."""
from datetime import datetime

import pandas as pd

from algoguard import live
from algoguard.data import make_synthetic
from algoguard.risk import GUARDED, RAW

P, V, I = make_synthetic(n_symbols=4, n_days=700, seed=2)
STRAT = "EMA Crossover (20/100)"


def _start(monkeypatch, i=500):
    monkeypatch.setattr(live, "START", V.index[i])
    return V.index[i]


def test_flat_until_the_record_starts(monkeypatch):
    start = _start(monkeypatch)
    sig, res = live.forward(P, V, STRAT, GUARDED)
    assert (res.equity.loc[:start] == res.equity.iloc[0]).all()
    assert len(res.trades) and (pd.to_datetime(res.trades.entry_date) > start).all()


def test_ledger_is_append_only(monkeypatch, tmp_path):
    _start(monkeypatch)
    sig, res = live.forward(P, V, STRAT, GUARDED)
    rows = live.day_rows("p", sig, res, V, I)
    path = tmp_path / "ledger.csv"
    added, _ = live.append_ledger(rows.iloc[:50], path)
    assert added == 50
    changed = rows.copy()
    changed.loc[changed.index[:50], "value_rs"] += 1000  # a later recomputation (e.g. revised prices) disagrees
    added, drift = live.append_ledger(changed, path)
    stored = pd.read_csv(path)
    assert added == len(rows) - 50 and len(stored) == len(rows)
    assert abs(drift - 1000) < 1e-6
    assert (stored.value_rs.iloc[:50].round(2) == rows.value_rs.iloc[:50].round(2)).all()  # old rows kept as recorded


def test_plan_blocks_entries_when_vix_is_high(monkeypatch):
    _start(monkeypatch)
    high = pd.Series(99.0, index=V.index)
    sig, res = live.forward(P, high, STRAT, GUARDED)
    plan = live.plan_next_open("p", sig, res, high)
    wanted = [s for s in sig.columns if sig[s].iloc[-1] == 1]
    assert wanted and {o["stock"] for o in plan} == {s.replace(".NS", "") for s in wanted}
    assert all(o["action"] == "BLOCKED" and "VIX" in o["why"] for o in plan)
    sig, res = live.forward(P, V, STRAT, RAW)
    assert all(o["action"] in ("HOLD", "BUY", "SELL") for o in live.plan_next_open("p", sig, res, V))


def test_todays_bar_is_ignored_until_it_is_final():
    day = V.index[-1]
    morning = datetime(day.year, day.month, day.day, 11, 0, tzinfo=live.IST)
    evening = datetime(day.year, day.month, day.day, 18, 0, tzinfo=live.IST)
    p, v, i = live.drop_unfinished(P, V, I, now=morning)
    assert v.index[-1] < day and all(df.index[-1] < day for df in p.values())
    p, v, i = live.drop_unfinished(P, V, I, now=evening)
    assert v.index[-1] == day
