"""VolSelect site: the live market (forward paper-trading record, plan for the next open, delayed
quotes) and the volatility-aware NIFTY 50 stock-selection study.

    streamlit run volselect_app.py   # this site
    streamlit run app.py             # the other site: the AlgoGuard risk-layer dashboard
"""
import streamlit as st

from algoguard.sites import ALGOGUARD_URL

pages = [st.Page("views/live_market.py", title="Live market", icon=":material/monitoring:", default=True),
         st.Page("views/volatility_selection.py", title="Volatility selection", icon=":material/insights:")]
nav = st.navigation(pages)
with st.sidebar:
    st.caption(f"The AlgoGuard risk-layer dashboard has its own site: [{ALGOGUARD_URL.split('//')[1]}]({ALGOGUARD_URL})")
nav.run()
