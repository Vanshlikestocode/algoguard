import numpy as np
import pandas as pd

from algoguard.backtest import run_backtest
from algoguard.broker import OrderRateLimiter, mpp_limit_price
from algoguard.data import make_synthetic
from algoguard.risk import GUARDED, RAW
from algoguard.strategies import STRATEGIES, build_signals, ema_crossover

P, V, I = make_synthetic(n_symbols=4, n_days=900, seed=1)


def test_no_lookahead():
    """Changing prices AFTER day k must not change anything up to day k."""
    sig = build_signals(P, ema_crossover)
    base = run_backtest(P, sig, V, GUARDED).equity
    k = 600
    P2 = {s: df.copy() for s, df in P.items()}
    for df in P2.values():
        df.iloc[k + 1:] *= 3.0
    sig2 = build_signals(P2, ema_crossover)
    alt = run_backtest(P2, sig2, V, GUARDED).equity
    assert np.allclose(base.iloc[: k + 1], alt.iloc[: k + 1])


def test_signals_are_binary():
    for fn in STRATEGIES.values():
        s = build_signals(P, fn)
        assert set(np.unique(s.values)) <= {0, 1}


def test_raw_has_no_interventions():
    r = run_backtest(P, build_signals(P, ema_crossover), V, RAW)
    assert r.events.empty and not r.blocked


def test_vix_rule_blocks_all_entries_when_vix_always_high():
    high_vix = pd.Series(99.0, index=V.index)
    r = run_backtest(P, build_signals(P, ema_crossover), high_vix, GUARDED)
    assert len(r.trades) == 0 and r.blocked.get("vix_limit", 0) > 0


def test_costs_reduce_equity():
    sig = build_signals(P, ema_crossover)
    cheap = run_backtest(P, sig, V, RAW, cost_rate=0).equity.iloc[-1]
    dear = run_backtest(P, sig, V, RAW, cost_rate=0.005).equity.iloc[-1]
    assert dear < cheap


def test_never_negative_cash_or_leverage():
    r = run_backtest(P, build_signals(P, ema_crossover), V, RAW)
    assert (r.exposure <= 1.0 + 1e-9).all()


def test_mpp_price_and_rate_limit():
    assert mpp_limit_price("BUY", 100.0) == 101.0
    assert mpp_limit_price("SELL", 100.0) == 99.0
    t = [0.0]
    lim = OrderRateLimiter(10, clock=lambda: t[0], sleep=lambda s: t.__setitem__(0, t[0] + s))
    for _ in range(25):
        lim.acquire()
    assert t[0] >= 2.0  # 25 orders at 10/s need at least 2 seconds


def test_breaker_block_only_never_force_sells():
    from dataclasses import replace
    sig = build_signals(P, ema_crossover)
    cfg = replace(GUARDED, max_drawdown=0.02, dd_flatten=False)
    r = run_backtest(P, sig, V, cfg)
    assert (r.events.action == "HALT").any()
    assert not (r.trades.exit_reason == "risk: flatten").any()
    flat = run_backtest(P, sig, V, replace(cfg, dd_flatten=True))
    assert (flat.trades.exit_reason == "risk: flatten").any()


def test_no_rebuy_after_stop_until_signal_resets():
    """A stopped-out stock is not bought back while the strategy still says 'long'."""
    from dataclasses import replace
    sig = build_signals(P, ema_crossover)
    r = run_backtest(P, sig, V, replace(RAW, enabled=True, stop_atr_mult=1.0))
    stops = r.trades[r.trades.exit_reason == "risk: ATR stop"]
    assert len(stops) > 0
    for _, st in stops.iterrows():
        later = r.trades[(r.trades.symbol == st.symbol) & (r.trades.entry_date > st.exit_date)]
        if len(later):
            nxt = later.entry_date.min()
            between = sig.loc[st.exit_date:nxt, st.symbol].iloc[:-1]
            assert (between == 0).any(), f"{st.symbol} re-bought on {nxt} without the signal resetting"
