import numpy as np
import pandas as pd

from algoguard.scanner import scan

D = pd.bdate_range("2024-01-01", periods=80)


def stock(daily_moves):
    close = 100 * np.cumprod(1 + np.array(daily_moves))
    return pd.DataFrame({"close": close}, index=D)


def alternating(size_first, size_last, switch=60):
    # +s, -s, +s ... so the volatility is exactly known; size changes at `switch`
    return [(size_first if t < switch else size_last) * (1 if t % 2 else -1) for t in range(80)]


def test_finds_stock_that_calms_down_while_vix_rises():
    prices = {"CALM.NS": stock(alternating(0.02, 0.002)), "WILD.NS": stock(alternating(0.005, 0.03))}
    vix = pd.Series(np.linspace(14, 20, 80), index=D)
    tbl, vix_chg = scan(prices, vix, D[-1], lookback=10)
    assert vix_chg > 0
    assert tbl.iloc[0].Stock == "CALM" and bool(tbl.iloc[0]["Calmer while VIX rose"])
    assert not bool(tbl.set_index("Stock").loc["WILD", "Calmer while VIX rose"])


def test_nothing_flagged_when_vix_falls():
    prices = {"CALM.NS": stock(alternating(0.02, 0.002))}
    vix = pd.Series(np.linspace(20, 14, 80), index=D)
    tbl, vix_chg = scan(prices, vix, D[-1], lookback=10)
    assert vix_chg < 0 and not tbl["Calmer while VIX rose"].any()
