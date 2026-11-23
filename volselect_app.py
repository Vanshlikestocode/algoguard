"""VolSelect site: NIFTY volatility and risk monitor. An overview, the live market (forward paper-trading
record, plan for the next open, delayed quotes) and the walk-forward research behind it.

    streamlit run volselect_app.py   # this site
    streamlit run app.py             # the other site: the AlgoGuard risk-layer dashboard
"""
import streamlit as st

from algoguard.sites import ALGOGUARD_URL

pages = [st.Page("views/overview.py", title="Overview", icon=":material/home:", default=True),
         st.Page("views/live_market.py", title="Live market", icon=":material/monitoring:"),
         st.Page("views/research.py", title="Research", icon=":material/insights:")]
nav = st.navigation(pages)
with st.sidebar:
    st.markdown("**VolSelect**  \nNIFTY volatility and risk monitor")
    st.caption("By Vansh Dave and Karthik Agarwal. Updated every trading day at 18:00 IST. Paper trading only; not investment advice.")
    st.caption(f"Companion site: the AlgoGuard risk layer at [{ALGOGUARD_URL.split('//')[1]}]({ALGOGUARD_URL})")
nav.run()
