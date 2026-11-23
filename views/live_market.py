"""Live market: delayed NSE prices that refresh on their own, the forward paper-trading record (one
committed row per trading day since the record began), the engine's plan for the next open, and
VolSelect's regime and ranking today. Reads live/ (written by live_update.py); research results untouched."""
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from algoguard.data import DEFAULT_TICKERS, INDEX_TICKER, VIX_TICKER
from algoguard.live import IST, LIVE, START
from views._ui import ACTION_COLOR, regime_label

st.set_page_config(page_title="VolSelect · Live market", page_icon=":material/monitoring:", layout="wide")
st.title("Live market")
st.caption("Paper trading only: no orders are sent anywhere. Not investment advice. Prices from Yahoo Finance, "
           "delayed by about 15 minutes.")

read = lambda name: json.loads((LIVE / name).read_text(encoding="utf-8")) if (LIVE / name).exists() else None
status, plan, vs_state = read("status.json"), read("plan.json"), read("vs_state.json")


# ---------------------------------------------------------------- 1. market now (refreshes itself)
@st.cache_data(ttl=300, show_spinner=False)
def quotes():
    import yfinance as yf
    syms = [INDEX_TICKER, VIX_TICKER] + DEFAULT_TICKERS
    raw = yf.download(syms, period="5d", interval="1d", auto_adjust=False, progress=False, group_by="ticker")
    rows = []
    for s in syms:
        c = raw[s]["Close"].dropna()
        if len(c) >= 2:
            rows.append({"symbol": s, "last": float(c.iloc[-1]), "change_pct": float(c.iloc[-1] / c.iloc[-2] - 1) * 100,
                         "as_of": c.index[-1].date().isoformat()})
    return pd.DataFrame(rows), datetime.now(IST).strftime("%d %b %Y, %H:%M IST")


@st.fragment(run_every="5m")
def market_now():
    st.subheader("Market now")
    if os.environ.get("ALGOGUARD_OFFLINE") == "1":
        st.info("Offline mode: live quotes are not fetched.")
        return
    try:
        q, fetched = quotes()
    except Exception as e:  # network or Yahoo hiccup: the rest of the page still works
        st.warning(f"Live quotes are unavailable right now ({type(e).__name__}). The record below is unaffected.")
        return
    if q.empty:
        st.warning("Yahoo returned no quotes right now; try again in a few minutes.")
        return
    q = q.set_index("symbol")
    c = st.columns(4)
    for col, sym, label in ((c[0], INDEX_TICKER, "NIFTY 50"), (c[1], VIX_TICKER, "India VIX")):
        if sym in q.index:
            col.metric(label, f"{q.loc[sym, 'last']:,.2f}", f"{q.loc[sym, 'change_pct']:+.2f}%",
                       delta_color="inverse" if sym == VIX_TICKER else "normal")
    up = (q.drop([INDEX_TICKER, VIX_TICKER], errors="ignore").change_pct > 0).sum()
    c[2].metric("Our 12 stocks up today", f"{up} of {len(q) - 2}")
    c[3].metric("Quotes fetched", fetched.split(", ")[1], help=f"{fetched}. Refreshes every 5 minutes while this page is open.")
    stocks = q.drop([INDEX_TICKER, VIX_TICKER], errors="ignore").reset_index()
    stocks["symbol"] = stocks["symbol"].str.replace(".NS", "", regex=False)
    st.dataframe(stocks.rename(columns={"symbol": "Stock", "last": "Last price (Rs)", "change_pct": "Change today %", "as_of": "Bar date"})
                 .style.format({"Last price (Rs)": "{:,.2f}", "Change today %": "{:+.2f}"}), hide_index=True, width="stretch", height=250)


market_now()

# ---------------------------------------------------------------- 2. volatility regime and ranking today
st.subheader("Volatility regime and resilience ranking")
if vs_state:
    c = st.columns(4)
    c[0].metric(f"{regime_label(vs_state['regime']).split(' ')[0]} Regime", vs_state["regime"].capitalize(),
                help="Calm below a 30% chance of high volatility over the next 10 sessions, rising 30–50%, high above 50%.")
    c[1].metric("High-vol chance", f"{vs_state['p_high']:.0%}", help="Chance that NIFTY's volatility over the next 10 sessions is high.")
    c[2].metric("India VIX", f"{vs_state['india_vix']:.2f}")
    c[3].metric("NIFTY vol, 20 days", f"{vs_state['nifty_realised_vol_20d']:.1f}%", help="Annualised realised volatility of NIFTY over the last 20 sessions.")
    rank = pd.read_csv(LIVE / "vs_ranking.csv").rename(columns={
        "rank": "Rank", "stock": "Stock", "sector": "Sector", "stress_score": "Resilience score", "momentum_120d_pct": "120-day return %",
        "volatility_20d_pct": "Volatility 20d %", "beta": "Beta", "in_top_10": "In top 10"})
    st.caption(f"Close of {pd.Timestamp(vs_state['date']):%d %b %Y}. Ranked by {vs_state['ranked_by']}; the model portfolio holds the "
               "top 10, inverse-volatility weighted. A research ranking, not a recommendation: out of sample it has not beaten "
               "equal-weight NIFTY 50 (see Research).")
    st.dataframe(rank.head(15).style.format({"Resilience score": "{:.3f}", "120-day return %": "{:+.1f}",
                                             "Volatility 20d %": "{:.1f}", "Beta": "{:.2f}"}), hide_index=True, width="stretch")
else:
    st.info("No VolSelect snapshot yet: run `python live_update.py`.")


# ---------------------------------------------------------------- 3. forward record
st.subheader(f"Forward paper-trading record since {START:%d %b %Y}")
st.markdown("Every trading day at 18:00 IST, after the NSE close, a scheduled job re-runs the same engine as the "
            "backtests on the latest prices and appends the day to `live/ledger.csv`. Rows are never rewritten and every "
            "day is a git commit, so the record is timestamped and cannot be edited after the fact. Rs 10 lakh per portfolio, "
            "0.15% cost per side, signals at the close, fills at the next open.")
if status:
    st.caption(f"Last update {status['updated_at_ist']} · last completed session {status['last_completed_session']}"
               + (f" · Yahoo later revised past prices by up to Rs {status['largest_restatement_rs']:,.0f}; stored rows are kept as recorded"
                  if status.get("largest_restatement_rs", 0) > 1 else ""))

ledger = pd.read_csv(LIVE / "ledger.csv", parse_dates=["date"]) if (LIVE / "ledger.csv").exists() else pd.DataFrame()
if ledger.empty:
    st.info(f"The record starts at the close of {START:%d %b %Y}. The first row appears after that evening's 18:00 IST "
            "update; the first trades fill at the next morning's open.")
else:
    piv = ledger.pivot_table(index="date", columns="portfolio", values="value_rs")
    nifty = ledger.groupby("date").nifty_close.first()
    fig = go.Figure()
    for col in piv.columns:
        fig.add_trace(go.Scatter(x=piv.index, y=piv[col] / 1e5, name=col, mode="lines+markers"))
    fig.add_trace(go.Scatter(x=nifty.index, y=10 * nifty / nifty.iloc[0], name="NIFTY 50 (same Rs 10 lakh)",
                             line=dict(dash="dash", color="#8A8A8A")))
    fig.update_layout(height=380, yaxis_title="Value (Rs lakh)", legend=dict(orientation="h", y=1.12), margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, width="stretch")
    last = ledger[ledger.date == ledger.date.max()].set_index("portfolio")
    summary = pd.DataFrame({"Value (Rs)": last.value_rs, "Return since start %": (last.value_rs / 1e6 - 1) * 100,
                            "Today %": last.day_return_pct, "Invested %": last.invested_pct, "Holding": last.holding_at_close.fillna("–")})
    st.dataframe(summary.style.format({"Value (Rs)": "{:,.0f}", "Return since start %": "{:+.2f}", "Today %": "{:+.2f}",
                                      "Invested %": "{:.0f}"}), width="stretch")
    with st.expander("Daily ledger (every fill, block and rule event)"):
        st.dataframe(ledger.sort_values(["date", "portfolio"], ascending=[False, True]), hide_index=True, width="stretch", height=380)

# ---------------------------------------------------------------- 4. plan for the next open
st.subheader("Plan for the next open")
if not plan:
    st.info("No plan yet: run `python live_update.py`.")
else:
    st.caption(f"Decided at the close of {plan['after_close_of']}; executes at the next session's open.")
    orders = pd.DataFrame(plan["orders"])
    if orders.empty:
        st.markdown("No orders and no open positions yet.")
    else:
        pick = st.selectbox("Portfolio", sorted(orders.portfolio.unique()))
        o = orders[orders.portfolio == pick].drop(columns="portfolio")
        order = {"SELL": 0, "BUY": 1, "BLOCKED": 2, "WAIT": 3, "HOLD": 4}
        o = o.sort_values("action", key=lambda s: s.map(order))
        st.dataframe(o.style.map(lambda v: f"color: {ACTION_COLOR.get(v, 'inherit')}; font-weight: 600", subset=["action"]),
                     hide_index=True, width="stretch")
        n = o.action.value_counts()
        st.caption(" · ".join(f"{k}: {n.get(k, 0)}" for k in ("BUY", "SELL", "HOLD", "BLOCKED", "WAIT")))
    with st.expander("Raw strategy signals at the last close (which stocks each strategy wants to hold)"):
        for strat, names in plan.get("long_signals", {}).items():
            st.markdown(f"**{strat}:** {', '.join(names) if names else 'no stock'}")

