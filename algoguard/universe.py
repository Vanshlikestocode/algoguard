"""NIFTY 50 universe for the volatility-aware selection study.

Kept in data/nifty50/ so the original 12-stock study (data/*.csv) is never touched.
The constituent list is NSE's current one (data/nifty50/ind_nifty50list.csv). Using today's
list for past years is survivorship bias; NSE does not publish free point-in-time lists.
Stocks that listed after 2012 simply join on their first trading day (ragged panel).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import data

DIR = data.DATA_DIR / "nifty50"
LIST = DIR / "ind_nifty50list.csv"
DEFENSIVE = {"Fast Moving Consumer Goods", "Healthcare", "Information Technology", "Power", "Telecommunication"}


def constituents() -> pd.DataFrame:
    df = pd.read_csv(LIST)
    df["ticker"] = df["Symbol"].str.strip() + ".NS"
    df["defensive"] = df["Industry"].isin(DEFENSIVE)
    return df[["ticker", "Company Name", "Industry", "defensive"]]


def download(start="2012-01-01", force=False, folder=None):
    import yfinance as yf
    folder = Path(folder or DIR)
    folder.mkdir(parents=True, exist_ok=True)
    for t in list(constituents().ticker) + [data.INDEX_TICKER, data.VIX_TICKER]:
        path = folder / f"{t.replace('^', 'IDX_')}.csv"
        if path.exists() and not force:
            continue
        raw = yf.download(t, start=start, auto_adjust=True, progress=False)
        if raw is None or raw.empty:
            print(f"  FAILED  {t}")
            continue
        data._clean(raw).to_csv(path)
        print(f"  saved   {t} ({len(raw)} rows)")


def load(folder=None):
    """Return (prices dict of OHLCV frames on their own dates, NIFTY frame, VIX close series)."""
    folder = Path(folder or DIR)
    prices = {}
    for t in constituents().ticker:
        df = data.read_csv(folder / f"{t}.csv")
        if df is not None and {"open", "high", "low", "close", "volume"} <= set(df.columns):
            prices[t] = df
    nifty = data.read_csv(folder / "IDX_NSEI.csv")
    vix = data.read_csv(folder / "IDX_INDIAVIX.csv")["close"]
    return prices, nifty, vix
