"""VolSelect landing page: what it is, what the market looks like today, why the numbers can be trusted,
and what the evidence honestly shows. Every number is read from live/ and results/ at render time."""
import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitAPIException

from algoguard.live import LIVE, START
from algoguard.sites import ALGOGUARD_URL
from views._ui import EW, MAIN, NIFTY, STRESS, VS, pct, read_json, regime_label, table

st.set_page_config(page_title="VolSelect · NIFTY volatility and risk monitor", page_icon=":material/monitoring:", layout="wide")

vs_state, status = read_json(LIVE / "vs_state.json"), read_json(LIVE / "status.json")
ledger = pd.read_csv(LIVE / "ledger.csv") if (LIVE / "ledger.csv").exists() else pd.DataFrame()

# ---------------------------------------------------------------- hero
st.caption("VOLSELECT · NIFTY VOLATILITY AND RISK MONITOR")
st.title("Know when NIFTY volatility is turning, and which stocks hold up.")
st.markdown("A daily volatility-regime forecast, a stress-resilience ranking of all 50 NIFTY stocks and a live, timestamped "
            "paper-trading record, built on a walk-forward research engine that anyone can re-run and verify in one command.")
b = st.columns([1, 1, 1.6])
try:
    b[0].page_link("views/live_market.py", label="Open the live market", icon=":material/monitoring:")
    b[1].page_link("views/research.py", label="See the evidence", icon=":material/insights:")
except StreamlitAPIException:  # opened on its own rather than through volselect_app.py: no other pages to link
    pass

# ---------------------------------------------------------------- today
st.divider()
day = vs_state["date"] if vs_state else "–"
st.markdown(f"#### Market state at the close of {pd.Timestamp(day):%d %b %Y}" if vs_state else "#### Market state")
c = st.columns(4)
with c[0].container(border=True):
    dot = regime_label(vs_state["regime"]).split(" ")[0] if vs_state else ""
    st.metric(f"{dot} Regime", vs_state["regime"].capitalize() if vs_state else "–",
              help="Calm below a 30% chance of high volatility over the next 10 sessions, rising 30–50%, high above 50%.")
with c[1].container(border=True):
    st.metric("High-vol chance", f"{vs_state['p_high']:.0%}" if vs_state else "–",
              help="Probability that NIFTY's volatility over the next 10 sessions is high (above the 75th percentile of the last year).")
with c[2].container(border=True):
    st.metric("India VIX", f"{vs_state['india_vix']:.2f}" if vs_state else "–")
with c[3].container(border=True):
    days = ledger.date.nunique() if len(ledger) else 0
    st.metric("Live record" if days else "Live record starts", f"{days} day{'s' if days != 1 else ''}" if days else f"{START:%d %b}",
              help=f"Forward paper-trading record from the close of {START:%d %b %Y}; one committed row per trading day.")
if status:
    st.caption(f"Updated automatically every trading day at 18:00 IST, after the NSE close. Last update {status['updated_at_ist']} IST.")

# ---------------------------------------------------------------- what it does
st.divider()
st.markdown("#### What it does")
c = st.columns(3)
with c[0].container(border=True, height="stretch"):
    st.markdown(":material/speed: **Volatility regime forecast**")
    st.markdown("Each day: the probability that NIFTY's volatility over the next 10 sessions will be high, from India VIX, "
                "realised volatility and a GARCH model. Classified calm, rising or high.")
with c[1].container(border=True, height="stretch"):
    st.markdown(":material/shield: **Stress-resilience ranking**")
    st.markdown("All 50 NIFTY stocks ranked by how likely each is to beat the index when volatility rises, from 19 measures "
                "such as beta, sector, trend and momentum. In calm markets the ranking switches to momentum.")
with c[2].container(border=True, height="stretch"):
    st.markdown(":material/history_edu: **Live, tamper-evident record**")
    st.markdown("Six rules-based paper portfolios run on fresh prices every day. Each day is appended to a ledger and committed "
                "to git, so no result can be edited after the fact.")

# ---------------------------------------------------------------- why trust it
st.divider()
st.markdown("#### Why the numbers can be trusted")
acc = pd.read_csv(VS / "forecast_accuracy.csv", index_col=0)
ho = acc.iloc[-1]
c = st.columns(4)
c[0].markdown(":material/verified: **Re-run it yourself**  \n`python verify.py` re-runs every backtest from the bundled data "
              "and checks all 45 result files number by number.")
c[1].markdown(":material/event_repeat: **Walk-forward only**  \nEvery model is refitted each January on past data only; "
              "2022 onward is a hold-out the design never saw.")
c[2].markdown(":material/lock_clock: **Timestamped live record**  \nThe forward record is append-only and every day is a git commit.")
c[3].markdown(f":material/target: **Measured, not claimed**  \nRegime forecast on the 2022+ hold-out: {ho['hit_rate']:.0%} right "
              f"(naive rule {ho['naive_hit_rate']:.0%}), {ho['precision']:.0%} precision when it says high.")

# ---------------------------------------------------------------- evidence, honestly
st.divider()
st.markdown("#### What the evidence shows")
full, ho_t, cov, h1 = table("full"), table("hold-out"), table("covid"), table("2022")
gross = pd.read_csv(VS / "cost_sensitivity.csv", index_col=0)
g = lambda a: gross.loc[f"{a} | 0.00%", "CAGR % 2022+"]
c = st.columns(2)
with c[0].container(border=True):
    st.markdown(":green[**Where it helps: in sell-offs**]")
    st.markdown(f"- **COVID crash (Feb–Apr 2020):** regime switch {pct(cov.loc[MAIN, 'Period return %'])}, "
                f"NIFTY {pct(cov.loc[NIFTY, 'Period return %'])}, equal-weight NIFTY 50 {pct(cov.loc[EW, 'Period return %'])}.")
    st.markdown(f"- **2022 sell-off (Jan–Jun):** resilience model {pct(h1.loc[STRESS, 'Period return %'])}, "
                f"NIFTY {pct(h1.loc[NIFTY, 'Period return %'])}.")
    st.markdown(f"- **2016–2026:** regime switch {pct(full.loc[MAIN, 'CAGR %'])} a year against "
                f"{pct(full.loc[NIFTY, 'CAGR %'])} for NIFTY buy and hold, with a smaller worst fall "
                f"({pct(full.loc[MAIN, 'Max drawdown %'])} against {pct(full.loc[NIFTY, 'Max drawdown %'])}).")
with c[1].container(border=True):
    st.markdown(":orange[**Where it does not, yet**]")
    st.markdown(f"- **Equal weight is hard to beat:** over 2016–2026 simply holding all 50 stocks earned {pct(full.loc[EW, 'CAGR %'])} a year.")
    st.markdown(f"- **No edge since 2022, even before costs:** {pct(g(MAIN))} a year against {pct(g(EW))} for equal weight.")
    st.markdown(f"- **Costs matter:** weekly rebalancing turns the portfolio over about {full.loc[MAIN, 'Turnover (x/yr)']:.0f} times a year.")
    st.markdown("That is why VolSelect is offered as a **risk monitor with a live, verifiable record**, not as a promise of returns.")

# ---------------------------------------------------------------- who it is for
st.divider()
st.markdown("#### Built for")
c = st.columns(3)
c[0].markdown(":material/account_balance: **Brokers and algo platforms**  \nA daily volatility-regime signal and stress view for "
              "risk desks and client dashboards, alongside the AlgoGuard risk layer.")
c[1].markdown(":material/query_stats: **Research and advisory teams**  \nA transparent, re-runnable baseline to test their own "
              "selection ideas against, with walk-forward discipline built in.")
c[2].markdown(":material/school: **Investors learning risk**  \nSee how rules behave day by day in real markets, with every "
              "decision explained.")

st.divider()
st.caption(f"Academic research prototype (student B.Tech AI project). Not investment advice; nothing here "
           f"is an offer of any service. Selling stock selections in India requires SEBI Research Analyst registration. "
           f"Companion site: the AlgoGuard risk layer at [{ALGOGUARD_URL.split('//')[1]}]({ALGOGUARD_URL}). "
           f"Code and data: [github.com/Vanshlikestocode/algoguard](https://github.com/Vanshlikestocode/algoguard).")
