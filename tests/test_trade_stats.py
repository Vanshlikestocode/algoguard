import pandas as pd

from algoguard.metrics import calendar_returns, trade_stats


def test_trade_stats_counts_and_ratios():
    t = pd.DataFrame({"pnl": [300.0, -100.0, -100.0, 200.0, 0.0],
                      "ret": [0.03, -0.01, -0.01, 0.02, 0.0],
                      "entry_date": pd.to_datetime(["2020-01-01"] * 5),
                      "exit_date": pd.to_datetime(["2020-01-11"] * 5)})
    s = trade_stats(t)
    assert (s["Wins"], s["Losses"]) == (2, 3)          # a break-even trade counts as a loss
    assert abs(s["Win rate %"] - 40) < 1e-9
    assert abs(s["Profit factor"] - 2.5) < 1e-9        # 500 won / 200 lost
    assert s["Max losing streak (trades)"] == 2
    assert s["Avg holding (calendar days)"] == 10


def test_calendar_returns():
    e = pd.Series([100.0, 110.0, 121.0], index=pd.to_datetime(["2020-01-02", "2020-12-31", "2021-12-31"]))
    r = calendar_returns(e)
    assert abs(r[2020] - 10) < 1e-9 and abs(r[2021] - 10) < 1e-9
