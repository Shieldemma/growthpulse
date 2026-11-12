import streamlit as st

from growthpulse import paths
from growthpulse.datagen import schema
from lib import data, ui


def render():
    ui.header("Methodology and Data Dictionary")
    t1, t2, t3 = st.tabs(["Methodology", "Data dictionary (raw tables)", "Metric definitions"])
    with t1:
        p = paths.ROOT / "docs" / "methodology.md"
        st.markdown(p.read_text() if p.exists() else "docs/methodology.md not found.")
    with t2:
        for name, spec in schema.TABLES.items():
            with st.expander(f"{name}  -  {spec['grain']}"):
                st.dataframe([{"column": c, "type": t, "description": d} for c, t, d in spec["columns"]], width="stretch", hide_index=True)
        p = paths.ROOT / "docs" / "data_dictionary.md"
        if p.exists():
            with st.expander("Warehouse models (staging, intermediate, marts)"):
                st.markdown(p.read_text())
    with t3:
        st.markdown("""
| Metric | Definition | Notes |
|---|---|---|
| CPC | spend / clicks | n/a when clicks = 0 |
| Paid-media CAC | media spend / new paying customers | n/a if no customers |
| Fully loaded CAC | (media + allocated overhead) / new paying customers | overhead allocated pro-rata to paid spend |
| ROAS | net revenue in window / media spend | not profit; not causal |
| Observed LTV | net revenue collected per customer in the window | refunds netted; censored cohorts excluded |
| Projected LTV | gross margin x revenue, constant churn after month 12, 36 months, 10% discount | a MODEL |
| LTV:CAC | gross-profit LTV / CAC | >3 is a rule of thumb, not a law |
| Retention(k) | customers paying in cycle k / customers observable at k | |
| Incremental lift | treatment rate - control rate (ITT) | the only causal measure here |
""")
