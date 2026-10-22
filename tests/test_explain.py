from algoguard.backtest import run_backtest
from algoguard.data import make_synthetic
from algoguard.explain import explain_day
from algoguard.risk import GUARDED
from algoguard.strategies import build_signals, ema_crossover

P, V, _ = make_synthetic(n_symbols=4, n_days=900, seed=1)
R = run_backtest(P, build_signals(P, ema_crossover), V, GUARDED)


def test_cooldown_day_is_explained():
    day = R.events[R.events.action == "COOLDOWN"].date.iloc[0]
    text = " ".join(explain_day(R, day, V))
    assert "daily limit" in text and "no new buying" in text


def test_blocked_entry_names_the_stock_and_reason():
    ev = R.events[R.events.action == "BLOCKED ENTRY"].iloc[0]
    text = " ".join(explain_day(R, ev.date))
    assert ev.detail in text and "Wanted to buy" in text


def test_quiet_and_closed_days():
    busy = set(R.events.date) | set(R.trades.entry_date) | set(R.trades.exit_date)
    quiet = next(d for d in R.equity.index[300:] if d not in busy)
    assert any("quiet day" in s for s in explain_day(R, quiet))
    sat = R.equity.index[300] + __import__("pandas").Timedelta(days=(5 - R.equity.index[300].weekday()) % 7 or 7)
    assert explain_day(R, sat)[0].startswith("Markets were closed")
