"""AlgoGuard site (algoguard.streamlit.app): the enforceable risk-layer dashboard.

    streamlit run app.py             # this site
    streamlit run volselect_app.py   # the other site: live market + volatility selection
"""
import streamlit as st

from algoguard.sites import VOLSELECT_URL

with st.sidebar:
    st.caption(f"Live market and volatility selection have their own site: [{VOLSELECT_URL.split('//')[1]}]({VOLSELECT_URL})")
st.navigation([st.Page("views/algoguard_dashboard.py", title="AlgoGuard", default=True)], position="hidden").run()
