"""GrowthPulse dashboard.  Run from the project folder:  streamlit run app/streamlit_app.py"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                    # lets pages import `lib` and `views`
sys.path.insert(0, str(HERE.parent / "src"))     # lets pages import `growthpulse`

import streamlit as st

st.set_page_config(page_title="GrowthPulse", page_icon="📈", layout="wide")

from views import (p01_executive, p02_channels, p03_funnel, p04_unit_economics, p05_cohorts,  # noqa: E402
                   p06_attribution, p07_incrementality, p08_mmm, p09_quality, p10_methodology)

PAGES = [
    st.Page(p01_executive.render, title="Executive Overview", icon="🏠", url_path="executive", default=True),
    st.Page(p02_channels.render, title="Channel Performance", icon="📣", url_path="channels"),
    st.Page(p03_funnel.render, title="Acquisition Funnel", icon="🔻", url_path="funnel"),
    st.Page(p04_unit_economics.render, title="CAC, LTV and ROAS", icon="💰", url_path="unit-economics"),
    st.Page(p05_cohorts.render, title="Cohorts and Retention", icon="🧬", url_path="cohorts"),
    st.Page(p06_attribution.render, title="Attribution Comparison", icon="🔀", url_path="attribution"),
    st.Page(p07_incrementality.render, title="Incrementality Experiment", icon="🧪", url_path="incrementality"),
    st.Page(p08_mmm.render, title="Marketing Mix Modelling", icon="📊", url_path="mmm"),
    st.Page(p09_quality.render, title="Data Quality and Pipeline", icon="✅", url_path="quality"),
    st.Page(p10_methodology.render, title="Methodology and Dictionary", icon="📚", url_path="methodology"),
]
st.navigation(PAGES).run()
