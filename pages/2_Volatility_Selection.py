"""Volatility-aware NIFTY 50 stock selection: results of `python run_vs.py` (reads results/vs/)."""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

R = Path(__file__).resolve().parent.parent / "results" / "vs"
st.set_page_config(page_title="Volatility selection · AlgoGuard", layout="wide")
st.title("Volatility-aware NIFTY 50 stock selection")
st.warning("**Academic research prototype, not investment advice.** Backtest results do not predict future returns. "
           "Offering stock selections to anyone would require SEBI Research Analyst registration.")

if not (R / "current_state.json").exists():
    st.error("No results yet. Run `python run_vs.py --download` first.")
    st.stop()

state = json.loads((R / "current_state.json").read_text())
rank = pd.read_csv(R / "current_ranking.csv", index_col=0)
eq = pd.read_csv(R / "equity_curves.csv", index_col=0, parse_dates=True)
reg = pd.read_csv(R / "regime_forecast.csv", index_col=0, parse_dates=True)
log = pd.read_csv(R / "audit_log_vs.csv", parse_dates=["date"])

st.subheader(f"Current volatility regime ({state['date']})")
c = st.columns(4)
c[0].metric("Regime", state["regime"].upper())
c[1].metric("Probability of high volatility, next 10 days", f"{state['p_high']:.0%}")
c[2].metric("India VIX", f"{state['vix']:.2f}")
c[3].metric("NIFTY volatility, last 20 days", f"{state['rv20']:.1f}%")
st.caption("Calm below 30% probability, rising 30–50%, high above 50%. The model is refitted every January on past data only.")

stressed = state["regime"] in ("rising", "high")
st.subheader("Ranked stocks " + ("(resilience model: rising/high volatility)" if stressed else "(momentum: calm market)"))
show = rank.sort_values("stress_score" if stressed else "momentum_120d_%", ascending=False).head(state["k"])
show = show.rename(columns={"stress_score": "Chance of beating NIFTY (stress model)", "momentum_120d_%": "120-day return %",
                            "volatility_20d_%": "Volatility 20d %", "beta": "Beta", "defensive": "Defensive sector",
                            "top_reasons": "Main reasons (feature, + helps / − hurts)"})
show.index = show.index.str.replace(".NS", "")
st.dataframe(show.style.format({"Chance of beating NIFTY (stress model)": "{:.0%}", "120-day return %": "{:.1f}",
                                "Volatility 20d %": "{:.1f}", "Beta": "{:.2f}"}), use_container_width=True)
st.caption("A research ranking from historical patterns, not a recommendation to buy.")

st.subheader("Walk-forward equity vs benchmarks")
pick = st.multiselect("Approaches", list(eq.columns), default=[state["headline"], "Equal-weight NIFTY 50 (benchmark)",
                                                                 "NIFTY 50 buy and hold (benchmark)"])
fig = go.Figure()
for col in pick:
    fig.add_trace(go.Scatter(x=eq.index, y=eq[col], name=col))
fig.add_vline(x=pd.Timestamp("2022-01-01"), line_dash="dot")
fig.update_layout(height=420, yaxis_type="log", yaxis_title="Portfolio value (Rs, log)", legend=dict(orientation="h", y=1.08),
                  margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, use_container_width=True)
st.caption("Dotted line: start of the 2022+ hold-out.")

st.subheader("Drawdown")
fig = go.Figure()
for col in pick:
    fig.add_trace(go.Scatter(x=eq.index, y=(eq[col] / eq[col].cummax() - 1) * 100, name=col))
fig.update_layout(height=300, yaxis_title="Drawdown %", legend=dict(orientation="h", y=1.1), margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, use_container_width=True)

t1, t2, t3, t4 = st.tabs(["Results tables", "Volatility forecast", "Audit log", "Charts for slides"])
with t1:
    for f in sorted(R.glob("table_*.csv")):
        st.markdown(f"**{f.stem.replace('table_', '').capitalize()}**")
        st.dataframe(pd.read_csv(f, index_col=0).round(2), use_container_width=True)
with t2:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=reg.index, y=reg["p_high"], name="Forecast probability of high volatility", fill="tozeroy"))
    fig.add_trace(go.Scatter(x=reg.index, y=reg["fwd_rv"], name="Actual volatility next 10 days %", yaxis="y2"))
    fig.update_layout(height=360, yaxis=dict(title="Probability", range=[0, 1]),
                      yaxis2=dict(title="Volatility %", overlaying="y", side="right"), legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown((R / "report.md").read_text().split("## Volatility forecast accuracy")[1].split("## Drawdown trigger")[0])
with t3:
    st.caption("Every yearly retrain and every drawdown re-evaluation, with the reason. The portfolio never goes to cash.")
    st.dataframe(log.sort_values("date", ascending=False), use_container_width=True, height=420)
with t4:
    for f in sorted(R.glob("chart_*.png")):
        st.image(str(f))
