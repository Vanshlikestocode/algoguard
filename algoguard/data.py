"""Market data: real NSE data via yfinance (cached to CSV), or a synthetic demo set.

Real data is the default. The synthetic generator exists so the whole pipeline can be
tested offline; never present synthetic results as market results.
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# Large, liquid NIFTY 50 constituents. Note: using today's large caps introduces
# survivorship bias over a 2012+ backtest. This is stated as a limitation.
DEFAULT_TICKERS = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS", "ITC.NS",
    "LT.NS", "SBIN.NS", "BHARTIARTL.NS", "AXISBANK.NS", "KOTAKBANK.NS", "HINDUNILVR.NS",
]
INDEX_TICKER = "^NSEI"
VIX_TICKER = "^INDIAVIX"

DATA_DIR = Path(os.environ.get("ALGOGUARD_DATA", Path(__file__).resolve().parent.parent / "data"))


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df = df[~df.index.duplicated()].sort_index()
    df = df.replace(0, np.nan).dropna(subset=["open", "high", "low", "close"])
    return df


def download(tickers=None, start="2012-01-01", end=None, force=False) -> None:
    """Download daily OHLCV for tickers + NIFTY + India VIX into DATA_DIR as CSV."""
    import yfinance as yf  # imported lazily so the package works offline

    tickers = list(tickers or DEFAULT_TICKERS)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for t in tickers + [INDEX_TICKER, VIX_TICKER]:
        path = DATA_DIR / f"{t.replace('^', 'IDX_')}.csv"
        if path.exists() and not force and read_csv(path) is not None:
            print(f"  cached  {t}")
            continue
        raw = yf.download(t, start=start, end=end, auto_adjust=True, progress=False)
        if raw is None or raw.empty:
            print(f"  FAILED  {t} (no data returned)")
            continue
        _clean(raw).to_csv(path)
        print(f"  saved   {t}  ({len(raw)} rows)")


def read_csv(path: Path) -> pd.DataFrame | None:
    """Read a cached CSV defensively: tolerate extra header rows (older yfinance
    exports), coerce dates and numbers, drop anything unparseable."""
    try:
        df = pd.read_csv(path, index_col=0)
    except Exception:
        return None
    df.columns = [str(c).lower() for c in df.columns]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df.index = pd.to_datetime(df.index, errors="coerce", utc=True).tz_localize(None).normalize()
    df = df[df.index.notna()]
    df = df.apply(pd.to_numeric, errors="coerce")
    if "close" not in df:
        return None
    df = df.dropna(subset=["close"])
    df = df[~df.index.duplicated()].sort_index()
    return df if len(df) > 50 else None


def load_real(tickers=None):
    tickers = list(tickers or DEFAULT_TICKERS)
    prices = {}
    for t in tickers:
        path = DATA_DIR / f"{t}.csv"
        if path.exists():
            df = read_csv(path)
            if df is None or not {"open", "high", "low"} <= set(df.columns):
                print(f"  WARNING: {path.name} is unreadable, skipping (re-download with --force)")
                continue
            prices[t] = df
    if not prices:
        raise FileNotFoundError(
            f"No price CSVs in {DATA_DIR}. Run:  python run.py --download"
        )
    vix_df = read_csv(DATA_DIR / f"{VIX_TICKER.replace('^', 'IDX_')}.csv")
    index = read_csv(DATA_DIR / f"{INDEX_TICKER.replace('^', 'IDX_')}.csv")
    vix = vix_df["close"] if vix_df is not None else None
    if vix is None:
        print("  WARNING: India VIX data missing; the VIX filter will never fire")
    if index is None:
        print("  WARNING: NIFTY 50 data missing; benchmark will be equal-weight buy & hold of the stocks")
    return align(prices, vix, index)


def align(prices: dict, vix: pd.Series | None, index: pd.DataFrame | None):
    """Restrict all series to common trading dates (no forward-filled prices)."""
    common = None
    for df in prices.values():
        common = df.index if common is None else common.intersection(df.index)
    prices = {k: v.loc[common] for k, v in prices.items()}
    if vix is not None:
        vix = vix.reindex(common).ffill()  # VIX is a level, carrying the last print is fine
    if index is not None:
        index = index.reindex(common).ffill()
    return prices, vix, index


def make_synthetic(n_symbols=12, n_days=3400, seed=7):
    """Regime-switching GBM with volatility clustering and occasional crash days.

    Produces OHLC per symbol, a synthetic 'VIX' derived from market volatility and an
    equal-weight index. For pipeline testing only.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2012-01-02", periods=n_days)
    # market regime: 0 calm, 1 stressed
    regime = np.zeros(n_days, dtype=int)
    for t in range(1, n_days):
        p_switch = 0.01 if regime[t - 1] == 0 else 0.04
        regime[t] = 1 - regime[t - 1] if rng.random() < p_switch else regime[t - 1]
    mkt_vol = np.where(regime == 1, 0.024, 0.009)
    mkt_drift = np.where(regime == 1, -0.0012, 0.0006)
    mkt = mkt_drift + mkt_vol * rng.standard_t(4, n_days) / np.sqrt(2)
    crash = rng.random(n_days) < 0.003
    mkt[crash] -= rng.uniform(0.03, 0.08, crash.sum())

    prices = {}
    for i in range(n_symbols):
        beta = rng.uniform(0.7, 1.3)
        idio = rng.normal(0.0002, rng.uniform(0.008, 0.015), n_days)
        # mild trend persistence so trend strategies have something to find
        trend = np.convolve(rng.normal(0, 0.0015, n_days), np.ones(60) / 60, mode="same")
        r = beta * mkt + idio + trend
        close = 100 * rng.uniform(0.5, 5) * np.exp(np.cumsum(r))
        gap = rng.normal(0, 0.004, n_days) + 0.5 * mkt
        open_ = close * np.exp(-r + gap)  # open sits between previous close and today
        rng_hl = np.abs(rng.normal(0, mkt_vol * 0.8 + 0.004, n_days))
        high = np.maximum(open_, close) * (1 + rng_hl)
        low = np.minimum(open_, close) * (1 - rng_hl)
        prices[f"SYN{i:02d}"] = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close,
             "volume": rng.integers(1e5, 1e6, n_days)}, index=dates)

    realized = pd.Series(mkt, index=dates).rolling(20, min_periods=5).std() * np.sqrt(252) * 100
    vix = (realized * 1.15 + 3).bfill().clip(lower=9)
    index_close = pd.DataFrame({k: v["close"] for k, v in prices.items()}).pct_change().mean(axis=1)
    index = pd.DataFrame({"close": 10000 * (1 + index_close.fillna(0)).cumprod()})
    return prices, vix, index
