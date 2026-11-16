"""Entry point of the dashboard.  Start with:   streamlit run dashboard/app.py

Holds only the navigation: the pages are tabs at the top of the screen, the sidebar is left for the filters.  Every page is a
script of its own (dashboard/home.py and dashboard/pages/*.py) and also runs on its own, which the tests rely on.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # streamlit only adds dashboard/ to the path

import streamlit as st  # noqa: E402

PAGES = [st.Page("home.py", title="Home", icon="🏠", default=True),
         st.Page("pages/1_Reddit_Volume.py", title="Reddit Volume and Ticker Mentions"),
         st.Page("pages/3_Price_and_Return.py", title="Price and Return"),
         st.Page("pages/5_Market_and_Sentiment.py", title="Market and Sentiment"),
         st.Page("pages/6_Statistical_Analysis.py", title="Statistical Analysis"),
         st.Page("pages/9_Logistic_Regression.py", title="Logistic Regression"),
         st.Page("pages/8_Hot_Events.py", title="Hot Events")]

try:
    st.navigation(PAGES, position="top").run()
finally:                                              # also when a page ends early with st.stop(): the disclaimer is always the last thing on the page
    from dashboard import common  # noqa: E402
    common.footer()
