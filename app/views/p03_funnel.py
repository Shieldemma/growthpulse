import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import streamlit as st

from growthpulse import metrics as M, paths
from lib import data, filters, ui

STEPS = [("visitors", "Visitors"), ("pricing_viewers", "Viewed pricing"), ("signup_starters", "Started signup"),
         ("signups", "Completed signup"), ("trials", "Started trial"), ("paying_customers", "Became paying")]


def render():
    data.require_data()
    ui.header("Acquisition Funnel", "Where visitors drop out between first visit and paid subscription (visitors grouped by first-visit date and first-touch channel).")
    f = filters.sidebar(show_model=False, show_window=False)
    tab1, tab2 = st.tabs(["SaaS funnel (synthetic)", "GA4 e-commerce funnel (real public sample, BigQuery mode)"])
    with tab1:
        fn = data.table(paths.MARTS, "mart_growth_funnel")
        fn["first_session_date"] = pd.to_datetime(fn.first_session_date)
        fn = filters.apply(fn, f, date_col="first_session_date")
        if fn.empty:
            return ui.empty_state()
        dev = st.multiselect("Device", sorted(fn.device_category.unique()), default=sorted(fn.device_category.unique()))
        fn = fn[fn.device_category.isin(dev)]
        if fn.empty:
            return ui.empty_state()
        tot = fn[[s for s, _ in STEPS]].sum()
        fig = go.Figure(go.Funnel(y=[l for _, l in STEPS], x=[tot[s] for s, _ in STEPS], textinfo="value+percent previous"))
        fig.update_layout(title="Funnel (visitors who ever reached each step)", margin=dict(t=50))
        st.plotly_chart(fig, width="stretch")
        steps = pd.DataFrame({"step": [l for _, l in STEPS], "visitors": [tot[s] for s, _ in STEPS]})
        steps["conversion_from_previous"] = M.safe_divide(steps.visitors, steps.visitors.shift(1))
        steps["conversion_from_top"] = M.safe_divide(steps.visitors, steps.visitors.iloc[0])
        steps["drop_off_from_previous"] = 1 - steps.conversion_from_previous
        worst = steps.iloc[1:].sort_values("drop_off_from_previous", ascending=False).iloc[0]
        st.info(f"Largest relative drop-off: **{worst.step}** ({ui.fmt_pct(worst.drop_off_from_previous)} of the previous step did not continue).")
        st.dataframe(steps, width="stretch", hide_index=True, column_config={c: st.column_config.NumberColumn(format="%.3f") for c in ["conversion_from_previous", "conversion_from_top", "drop_off_from_previous"]})
        ui.download(steps, "funnel_steps")
        by = fn.groupby("channel_name")[[s for s, _ in STEPS]].sum()
        rates = pd.DataFrame({"visit_to_signup": M.safe_divide(by.signups, by.visitors), "signup_to_trial": M.safe_divide(by.trials, by.signups),
                              "trial_to_paid": M.safe_divide(by.paying_customers, by.trials), "visit_to_paid": M.safe_divide(by.paying_customers, by.visitors)}, index=by.index)
        st.plotly_chart(px.imshow(rates, text_auto=".1%", aspect="auto", color_continuous_scale="Blues", title="Step conversion by first-touch channel"), width="stretch")
        daily = fn.assign(m=fn.first_session_date.dt.to_period("M").dt.to_timestamp()).groupby("m")[["visitors", "signups", "paying_customers"]].sum().reset_index()
        daily["visit_to_signup"] = M.safe_divide(daily.signups, daily.visitors)
        st.plotly_chart(px.line(daily, x="m", y="visit_to_signup", markers=True, title="Visit-to-signup rate by first-visit month", labels={"m": "", "visit_to_signup": "rate"}), width="stretch")
        st.caption("Recent cohorts are right-censored: visitors from the last weeks have had less time to reach later steps.")
    with tab2:
        p = paths.DATA_PROCESSED / "ga4_funnel.csv"
        if not p.exists():
            st.info("**No GA4 data loaded.** The GA4 funnel needs BigQuery mode (dbt model `mart_ga4_funnel` on the public sample). "
                    "Follow `docs/bigquery_setup.md`, then run `python scripts/export_bigquery_marts.py` to place `data/processed/ga4_funnel.csv` here. "
                    "Status: **BigQuery integration is implemented but UNVERIFIED** (no cloud credentials were available when this project was built).")
        else:
            g = pd.read_csv(p)
            st.success("Loaded real GA4 sample funnel exported from BigQuery.")
            st.plotly_chart(go.Figure(go.Funnel(y=g.step_label, x=g.sessions, textinfo="value+percent previous")), width="stretch")
            st.dataframe(g, width="stretch", hide_index=True)
