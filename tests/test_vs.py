"""Tests for the volatility-aware selection study (synthetic data, so they run offline)."""
import numpy as np
import pandas as pd

from algoguard import features, portfolio, regime
from algoguard.data import make_synthetic

P, V, I = make_synthetic(n_symbols=6, n_days=900, seed=3)
NC = I["close"]
SECT = pd.DataFrame({"ticker": list(P), "defensive": [True, False] * 3})
K = 650  # perturb everything after this day


def bumped():
    P2 = {s: df.copy() for s, df in P.items()}
    for df in P2.values():
        df.iloc[K + 1:, :4] *= 3.0
    nc2 = NC.copy(); nc2.iloc[K + 1:] *= 3.0
    v2 = V.copy(); v2.iloc[K + 1:] *= 2.0
    return P2, nc2, v2


def test_features_have_no_lookahead():
    f = regime.base_frame(NC, V)
    a = features.panel(P, NC, f["rv10"] > f["thr"], SECT)
    P2, nc2, v2 = bumped()
    f2 = regime.base_frame(nc2, v2)
    b = features.panel(P2, nc2, f2["rv10"] > f2["thr"], SECT)
    day = NC.index[K]
    cols = features.FEATURES
    pd.testing.assert_frame_equal(a.loc[:day, cols], b.loc[:day, cols])


def test_regime_forecast_has_no_lookahead():
    a = regime.walk_forward(NC, V, 2014)
    P2, nc2, v2 = bumped()
    b = regime.walk_forward(nc2, v2, 2014)
    day = NC.index[K]
    assert a.loc[:day, "p_high"].notna().any()
    np.testing.assert_allclose(a.loc[:day, "p_high"].fillna(-1), b.loc[:day, "p_high"].fillna(-1))


def _inputs(prices):
    idx = NC.index[200:]
    O = pd.DataFrame({s: prices[s]["open"].reindex(idx) for s in prices})
    C = pd.DataFrame({s: prices[s]["close"].reindex(idx) for s in prices})
    vol = C.pct_change().rolling(20).std() * np.sqrt(252)
    mom = C.pct_change(60)
    return O, C, vol, {"momentum": mom, "stress": -vol, "low_vol": -vol, "equal_weight": vol.notna().astype(float),
                       "stress_gb": -vol}


def test_portfolio_has_no_lookahead():
    O, C, vol, sc = _inputs(P)
    a = portfolio.run(O, C, vol, sc, None, policy="momentum", k=3).equity
    P2, _, _ = bumped()
    O2, C2, vol2, sc2 = _inputs(P2)
    b = portfolio.run(O2, C2, vol2, sc2, None, policy="momentum", k=3).equity
    day = NC.index[K]
    np.testing.assert_allclose(a.loc[:day], b.loc[:day])


def test_drawdown_trigger_never_goes_to_cash_and_logs():
    O, C, vol, sc = _inputs(P)
    r = portfolio.run(O, C, vol, sc, None, policy="momentum", k=3, dd=0.03, cooldown=10)
    assert len(r.log) > 0 and (r.log.action == "RE-EVALUATE").all()
    invested = r.exposure[r.exposure.index >= r.exposure[r.exposure > 0].index[0]]
    assert invested.min() > 0.9  # fully invested apart from the cost buffer
    assert (r.exposure <= 1.0 + 1e-9).all()  # never leveraged


def test_equal_weight_holds_every_stock():
    O, C, vol, sc = _inputs(P)
    r = portfolio.run(O, C, vol, sc, None, policy="equal_weight", k=3)
    w = list(r.holdings.values())[-1]["weights"]
    assert len(w) == len(P) and abs(max(w.values()) - min(w.values())) < 1e-3
