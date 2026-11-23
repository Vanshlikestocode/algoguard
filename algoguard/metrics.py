import numpy as np
import pandas as pd


def drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1


def summarize(equity: pd.Series, trades: pd.DataFrame | None = None, exposure: pd.Series | None = None,
              rf: float = 0.065) -> dict:
    """Headline stats. rf = annual risk-free rate (approx. Indian T-bill) for Sharpe/Sortino."""
    equity = equity.dropna()
    if len(equity) < 3:
        return {}
    r = equity.pct_change().dropna()
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1
    vol = r.std() * np.sqrt(252)
    ex = r - rf / 252
    sharpe = ex.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan
    down = np.sqrt((np.minimum(ex, 0) ** 2).mean()) * np.sqrt(252)  # downside deviation below the risk-free rate
    sortino = (ex.mean() * 252) / down if down > 0 else np.nan
    mdd = drawdown(equity).min()
    out = {
        "CAGR %": cagr * 100,
        "Volatility %": vol * 100,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Max drawdown %": mdd * 100,
        "Calmar": cagr / abs(mdd) if mdd < 0 else np.nan,
        "Worst day %": r.min() * 100,
        "Days below -2% (count)": int((r <= -0.02).sum()),
        "95% daily VaR %": np.percentile(r, 5) * 100,
        "Final value (Rs lakh)": equity.iloc[-1] / 1e5,
    }
    if trades is not None and len(trades):
        wins = trades[trades.pnl > 0].pnl.sum()
        losses = -trades[trades.pnl < 0].pnl.sum()
        out.update({
            "Trades": len(trades),
            "Win rate %": (trades.pnl > 0).mean() * 100,
            "Profit factor": wins / losses if losses > 0 else np.nan,
        })
    if exposure is not None:
        out["Avg exposure %"] = exposure.mean() * 100
    return out


def trade_stats(trades: pd.DataFrame) -> dict:
    """Trade-level statistics from a trade list with columns pnl, ret, entry_date, exit_date.
    pnl is after costs on both sides, so a trade that only covered its costs counts as a loss."""
    if trades is None or not len(trades):
        return {"Trades": 0}
    pnl, ret = trades["pnl"], trades["ret"] * 100
    win, loss = pnl > 0, pnl <= 0
    streak = longest = 0
    for is_loss in loss.values:  # trades are logged in exit order
        streak = streak + 1 if is_loss else 0
        longest = max(longest, streak)
    avg_win, avg_loss = ret[win].mean(), ret[loss].mean()
    held = (pd.to_datetime(trades["exit_date"]) - pd.to_datetime(trades["entry_date"])).dt.days
    return {
        "Trades": len(trades),
        "Wins": int(win.sum()),
        "Losses": int(loss.sum()),
        "Win rate %": win.mean() * 100,
        "Win/loss count ratio": win.sum() / loss.sum() if loss.sum() else np.nan,
        "Avg win %": avg_win,
        "Avg loss %": avg_loss,
        "Payoff ratio (avg win / avg loss)": avg_win / abs(avg_loss) if loss.any() and avg_loss != 0 else np.nan,
        "Profit factor": pnl[win].sum() / -pnl[loss].sum() if pnl[loss].sum() < 0 else np.nan,
        "Expectancy per trade %": ret.mean(),
        "Expectancy per trade (Rs)": pnl.mean(),
        "Best trade %": ret.max(),
        "Worst trade %": ret.min(),
        "Max losing streak (trades)": longest,
        "Avg holding (calendar days)": held.mean(),
    }


def calendar_returns(equity: pd.Series) -> pd.Series:
    """Return % for each calendar year (first year from the first available value)."""
    e = equity.dropna()
    year_end = e.groupby(e.index.year).last()
    start = pd.concat([pd.Series([e.iloc[0]], index=[year_end.index[0]]), year_end.shift(1).iloc[1:]])
    return (year_end / start - 1) * 100
