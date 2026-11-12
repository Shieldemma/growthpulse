import pandas as pd
import plotly.express as px
import streamlit as st

from growthpulse import metrics as M, paths
from lib import data, filters, ui


def render():
    data.require_data()
    ui.header("Attribution Comparison", "The same customers, credited to channels by four different rules.")
    f = filters.sidebar(show_model=False)
    rows = []
    for mname, label in filters.MODELS.items():
        d = filters.apply(data.perf(mname), f)
        if d.empty:
            continue
        a = M.aggregate_performance(d, by=["channel_name"], window=f.window, gross_margin=f.gross_margin, data_end=f.data_end)
        a["model"] = label
        rows.append(a)
    if not rows:
        return ui.empty_state()
    a = pd.concat(rows, ignore_index=True)
    metric = st.radio("Compare", ["new_customers", "revenue_window", "cac", "roas_window"], horizontal=True,
                      format_func=lambda x: {"new_customers": "Credited customers", "revenue_window": "Attributed revenue (window)", "cac": "Paid-media CAC", "roas_window": "ROAS"}[x])
    plot = a[a[metric].notna()]
    if plot.empty:
        return ui.empty_state("Nothing to compare for this metric.", "Paid-only metrics (CAC, ROAS) need paid channels selected.")
    st.plotly_chart(px.bar(plot, x="channel_name", y=metric, color="model", barmode="group", labels={"channel_name": "", metric: metric}, title="Channel credit by attribution model"), width="stretch")
    w = a.pivot(index="channel_name", columns="model", values="new_customers")
    spread = ((w.max(axis=1) - w.min(axis=1)) / w.mean(axis=1)).rename("range_vs_mean").sort_values(ascending=False)
    c1, c2 = st.columns([2, 1])
    with c1:
        st.dataframe(w.round(1), width="stretch")
    with c2:
        st.dataframe(spread.map(lambda x: f"{x:.0%}"), width="stretch")
        st.caption("How much a channel's credit moves between models. Large = conclusions about it depend on the rule.")
    ui.download(a, "attribution_comparison")
    st.subheader("How to read this")
    st.markdown("""
- **First touch** rewards the channel that introduced the visitor (favours awareness channels).
- **Last touch** rewards the final touch before signup (favours direct, email, organic - the channels people use when they are already convinced).
- **Linear** splits credit equally across all touches in the lookback window.
- **Position-based (rule-based multi-touch)** gives 40% to first, 40% to last and shares 20% among the middle touches.

**Limitations.** These are bookkeeping rules. They cannot see customers who never clicked an ad, they ignore touches that were not tracked, and they do **not** show that a channel *caused* a signup. 
Use them to understand sensitivity, and use experiments (next page) to measure causal impact.
""")
