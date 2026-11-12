import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from growthpulse import metrics as M, paths
from lib import data, filters, ui


def render():
    data.require_data()
    ui.header("CAC, LTV and ROAS", "Unit economics by channel. Observed values and model estimates are labelled separately.")
    f = filters.sidebar()
    df = filters.apply(data.perf(f.model), f)
    if df.empty:
        return ui.empty_state()
    ch = M.aggregate_performance(df, by=["channel_name"], window=f.window, gross_margin=f.gross_margin, data_end=f.data_end)
    paid = ch[ch.spend_usd > 0].copy()
    un = data.table(paths.MARTS, "mart_channel_unit_economics", f"where attribution_model = '{f.model}'")
    un["acquisition_month"] = pd.to_datetime(un.acquisition_month)
    un = un[(un.acquisition_month >= f.start.to_period("M").to_timestamp()) & (un.acquisition_month <= f.end) & un.channel_name.isin(f.channels)]
    st.subheader("1. Customer Acquisition Cost")
    cmo = un[un.spend_usd > 0].groupby("acquisition_month").agg(spend=("spend_usd", "sum"), oh=("overhead_allocated_usd", "sum"), cust=("new_customers", "sum")).reset_index()
    cmo["Paid-media CAC"] = M.safe_divide(cmo.spend, cmo.cust)
    cmo["Fully loaded CAC"] = M.safe_divide(cmo.spend + cmo.oh, cmo.cust)
    if cmo.empty:
        ui.empty_state("No paid spend in the selection.")
    else:
        st.plotly_chart(px.line(cmo.melt(id_vars="acquisition_month", value_vars=["Paid-media CAC", "Fully loaded CAC"]), x="acquisition_month", y="value", color="variable",
                                markers=True, title="CAC by acquisition month (USD)", labels={"value": "USD", "acquisition_month": "", "variable": ""}), width="stretch")
        ui.definition("CAC", "**Paid-media CAC** = media spend / new paying customers. **Fully loaded CAC** = (media spend + team, tools, agency and creative costs allocated to paid channels pro-rata to spend) / new paying customers. "
                      "Organic and owned channels carry no media cost, so their CAC is *n/a* rather than a misleading 0.")
    st.subheader("2. Lifetime value and LTV:CAC")
    econ = data.table(paths.ANALYTICS, "channel_economics")
    if paid.empty or econ.empty:
        ui.empty_state("No paid channels or no economics table.")
    else:
        e = econ[econ.channel_name.isin(paid.channel_name)].copy()
        gm = f.gross_margin
        e["projected_gp_ltv_36m (model)"] = e.projected_gp_ltv_36m * gm / 0.8   # rescale if the user moved the margin slider
        e["ltv_cac_loaded"] = M.ltv_cac_ratio(e["projected_gp_ltv_36m (model)"], e.cac_fully_loaded)
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(e.sort_values("ltv_cac_loaded"), x="channel_name", y="ltv_cac_loaded", title="Projected 36-month gross-profit LTV : fully loaded CAC (ESTIMATE)",
                         labels={"ltv_cac_loaded": "ratio", "channel_name": ""})
            fig.add_hline(y=3, line_dash="dot", annotation_text="3:1 rule of thumb")
            fig.add_hline(y=1, line_dash="dot", line_color="red", annotation_text="1:1")
            st.plotly_chart(fig, width="stretch")
        with c2:
            ret = data.table(paths.MARTS, "mart_customer_retention")
            g = ret.groupby(["acquisition_channel", "months_since_start"]).agg(o=("customers_observed", "sum"), n=("net_revenue_usd", "sum")).reset_index()
            g["gp"] = M.safe_divide(g.n, g.o) * gm
            g["cum"] = g.sort_values("months_since_start").groupby("acquisition_channel").gp.cumsum()
            g = g[g.acquisition_channel.isin(paid.channel_name) & (g.months_since_start <= 24) & (g.o >= 30)]
            fig = px.line(g, x="months_since_start", y="cum", color="acquisition_channel", title="Cumulative gross profit per customer (observed) vs CAC", labels={"cum": "USD", "months_since_start": "months since first payment"})
            for _, r in e.iterrows():
                if pd.notna(r.cac_fully_loaded):
                    fig.add_hline(y=r.cac_fully_loaded, line_dash="dot", opacity=0.35)
            st.plotly_chart(fig, width="stretch")
            st.caption("Dotted lines = fully loaded CAC per channel. Where a curve crosses its line is the payback month.")
        view = e[["channel_name", "cac_paid_media", "cac_fully_loaded", "revenue_per_customer_window", "roas_window", "monthly_churn_hazard_m3_12",
                  "projected_gp_ltv_36m (model)", "ltv_cac_loaded", "payback_months_loaded"]]
        st.dataframe(view, width="stretch", hide_index=True)
        ui.download(view, "unit_economics")
        ui.definition("LTV", "**Observed LTV** = net revenue actually collected (shown as revenue per customer in the window; refunds netted). "
                      "**Projected LTV** is a *model*: 36 months of gross profit using the observed first-12-month revenue, then a constant monthly churn hazard estimated from months 3-12 and a 10% annual discount rate. "
                      "Revenue LTV and gross-profit LTV differ by the gross-margin assumption (slider).")
    st.subheader("3. Return on ad spend")
    if not paid.empty:
        st.plotly_chart(px.scatter(paid, x="spend_usd", y="roas_window", size="new_customers", color="channel_name", title="ROAS vs spend (bubble = customers)", labels={"roas_window": "ROAS", "spend_usd": "spend USD"}), width="stretch")
    ui.definition("ROAS", "ROAS = net revenue in the window / media spend, using attribution credit. **ROAS is not profit** (ignores margin, overhead and later churn) and **does not prove incrementality**: "
                  "a channel can get credit for customers who would have bought anyway. The Incrementality page measures that directly.")
