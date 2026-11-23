"""Research: the walk-forward evidence behind VolSelect, 2016-2026 (reads results/vs/, written by run_vs.py)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from views._ui import EW, MAIN, NIFTY, STRESS, VS, pct, read_json, table

st.set_page_config(page_title="VolSelect · Research", page_icon=":material/insights:", layout="wide")
st.title("Research: walk-forward evidence")
st.markdown("All 50 current NIFTY 50 stocks, 2016–2026. Every model is refitted each 1 January on past data only and traded "
            "for that year; 2022 onward is a hold-out. Top 10 stocks, weekly rebalance, inverse-volatility weights, 0.15% "
            "cost per side, signals at the close and fills at the next open. Reproduce it with `python run_vs.py`; "
            "check it with `python verify.py`.")

if not (VS / "table_full.csv").exists():
    st.error("No results yet. Run `python run_vs.py` first.")
    st.stop()

full, ho, cov, h1 = table("full"), table("hold-out"), table("covid"), table("2022")
eq = pd.read_csv(VS / "equity_curves.csv", index_col=0, parse_dates=True)
reg = pd.read_csv(VS / "regime_forecast.csv", index_col=0, parse_dates=True)
log = pd.read_csv(VS / "audit_log_vs.csv", parse_dates=["date"])

# ---------------------------------------------------------------- headline
c = st.columns(4)
c[0].metric("VolSelect a year", pct(full.loc[MAIN, "CAGR %"]), f"{full.loc[MAIN, 'CAGR %'] - full.loc[NIFTY, 'CAGR %']:+.1f} vs NIFTY",
            help="Regime switch, compound annual growth 2016–2026, after 0.15% costs per side.")
c[1].metric("Equal weight a year", pct(full.loc[EW, "CAGR %"]), "benchmark", delta_color="off",
            help="Holding all 50 NIFTY stocks equally, 2016–2026: the like-for-like benchmark to beat.")
c[2].metric("COVID crash", pct(cov.loc[MAIN, "Period return %"]),
            f"{cov.loc[MAIN, 'Period return %'] - cov.loc[NIFTY, 'Period return %']:+.1f} vs NIFTY", help="Regime switch, 14 Feb–30 Apr 2020.")
c[3].metric("2022 sell-off", pct(h1.loc[STRESS, "Period return %"]),
            f"{h1.loc[STRESS, 'Period return %'] - h1.loc[NIFTY, 'Period return %']:+.1f} vs NIFTY", help="Resilience model, Jan–Jun 2022.")
st.caption("Stock prices include dividends while NIFTY 50 (^NSEI) is a price index, so comparisons with NIFTY favour the stocks "
           "by about 1.2–1.5% a year; equal weight is the like-for-like benchmark. Today's NIFTY 50 list is used for every year "
           "(survivorship bias), which flatters every approach here, the benchmark included. Not investment advice.")

# ---------------------------------------------------------------- charts
st.subheader("Growth of Rs 10 lakh")
default = [x for x in (MAIN, EW, NIFTY) if x in eq.columns]
pick = st.multiselect("Approaches", list(eq.columns), default=default)
COLORS = {MAIN: "#1F6F8B", EW: "#C9A227", NIFTY: "#8A8A8A"}
fig = go.Figure()
for col in pick:
    fig.add_trace(go.Scatter(x=eq.index, y=eq[col] / 1e5, name=col.replace(" (benchmark)", ""), line=dict(color=COLORS.get(col))))
fig.add_vline(x=pd.Timestamp("2022-01-01"), line_dash="dot")
fig.add_annotation(x=pd.Timestamp("2022-01-01"), y=1, yref="paper", text="hold-out starts", showarrow=False, xanchor="left")
fig.update_layout(height=420, yaxis=dict(type="log", title="Rs lakh (log scale)", tickvals=[5, 7.5, 10, 15, 20, 30, 50, 75, 100, 150]),
                  legend=dict(orientation="h", y=1.1), margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, width="stretch")

st.subheader("Fall from the previous peak")
fig = go.Figure()
for col in pick:
    fig.add_trace(go.Scatter(x=eq.index, y=(eq[col] / eq[col].cummax() - 1) * 100, name=col.replace(" (benchmark)", ""),
                             line=dict(color=COLORS.get(col))))
fig.update_layout(height=300, yaxis_title="Drawdown %", legend=dict(orientation="h", y=1.12), margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------- detail
PERIOD_NAMES = {"full": "Full walk-forward 2016–2026", "development": "Development 2016–2021", "hold-out": "Hold-out 2022–2026",
                "covid": "COVID crash, 14 Feb–30 Apr 2020", "2022": "2022 sell-off, Jan–Jun"}
t = st.tabs(["Results by period", "Win/loss", "Costs", "Volatility forecast", "What held up", "Audit log", "Ranking, end of backtest", "Charts"])
with t[0]:
    for f, label in PERIOD_NAMES.items():
        st.markdown(f"**{label}**")
        st.dataframe(table(f).round(2), width="stretch")
with t[1]:
    st.caption("Weeks end on Friday. A pick is one stock held from one rebalance to the next; it wins if it beat NIFTY 50.")
    st.dataframe(pd.read_csv(VS / "win_loss.csv", index_col=0).round(1), width="stretch")
with t[2]:
    st.caption("CAGR at different costs per side. 0.00% = before any cost. From 2022 the regime switch trails equal weight even before costs.")
    st.dataframe(pd.read_csv(VS / "cost_sensitivity.csv", index_col=0).round(2), width="stretch")
with t[3]:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=reg.index, y=reg["p_high"], name="Forecast chance of high volatility", fill="tozeroy"))
    fig.add_trace(go.Scatter(x=reg.index, y=reg["fwd_rv"], name="Actual NIFTY volatility, next 10 days %", yaxis="y2"))
    fig.update_layout(height=360, yaxis=dict(title="Probability", range=[0, 1]),
                      yaxis2=dict(title="Volatility %", overlaying="y", side="right"), legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, width="stretch")
    st.dataframe(pd.read_csv(VS / "forecast_accuracy.csv", index_col=0).round(3), width="stretch")
    st.caption("Hit rate against a naive 'next 10 days like the last 10' rule. When the model says high it is usually right; "
               "it misses most high-volatility spells (low recall).")
with t[4]:
    st.caption("Average daily rank correlation (IC) of each indicator with the next 10-day return over NIFTY, on high-volatility days.")
    st.dataframe(pd.read_csv(VS / "overfitting_ic.csv", index_col=0).round(3), width="stretch")
with t[5]:
    st.caption("Every yearly retrain and every drawdown re-evaluation, with the reason. The portfolio never goes to cash.")
    st.dataframe(log.sort_values("date", ascending=False), width="stretch", height=420, hide_index=True)
with t[6]:
    state = read_json(VS / "current_state.json")
    st.caption(f"The research ranking at the end of the backtest ({state['date'] if state else '–'}). "
               "Today's ranking, updated every evening, is on the Live market page.")
    st.dataframe(pd.read_csv(VS / "current_ranking.csv", index_col=0).round(3), width="stretch")
with t[7]:
    for f in sorted(VS.glob("chart_*.png")):
        st.image(str(f))
