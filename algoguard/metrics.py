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
    down = r[r < 0].std() * np.sqrt(252)
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
