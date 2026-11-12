import pandas as pd
import plotly.express as px
import streamlit as st

from growthpulse import metrics as M, paths
from lib import data, filters, ui


def render():
    data.require_data()
    ui.header("Customer Cohorts and Retention", "Do customers acquired through each channel stay and pay? Cohort = month of first payment.")
    f = filters.sidebar(show_model=False, show_window=False)
    r = data.table(paths.MARTS, "mart_customer_retention")
    r["cohort_month"] = pd.to_datetime(r.cohort_month)
    r = r[(r.cohort_month >= f.start.to_period("M").to_timestamp()) & (r.cohort_month <= f.end) & r.acquisition_channel.isin(f.channels)]
    if r.empty:
        return ui.empty_state()
    max_k = st.slider("Months to show", 3, 36, 18)
    r = r[r.months_since_start <= max_k]
    cohort = r.groupby(["cohort_month", "months_since_start"]).agg(obs=("customers_observed", "sum"), ret=("customers_retained", "sum"), rev=("net_revenue_usd", "sum")).reset_index()
    cohort["retention"] = M.retention_rate(cohort.ret, cohort.obs)
    cohort = cohort[cohort.obs >= 10]       # hide tiny cells
    sizes = r[r.months_since_start == 0].groupby("cohort_month").customers_observed.sum()
    ui.kpis([("Cohorts shown", str(cohort.cohort_month.nunique()), None), ("Customers in cohorts", ui.fmt_num(sizes.sum()), None),
             ("Median 12-month retention", ui.fmt_pct(cohort[cohort.months_since_start == 12].retention.median()) if (cohort.months_since_start == 12).any() else "n/a", "Median across cohorts that are old enough")])
    heat = cohort.pivot(index="cohort_month", columns="months_since_start", values="retention")
    heat.index = heat.index.strftime("%Y-%m")
    st.plotly_chart(px.imshow(heat, aspect="auto", color_continuous_scale="Viridis", zmin=0, zmax=1, title="Retention by cohort (share of customers who paid in month k)",
                              labels=dict(x="months since first payment", y="cohort", color="retention")), width="stretch")
    st.caption("Blank cells = not yet observable or fewer than 10 customers. A customer counts at month k only if that billing cycle could already have happened by the data end.")
    ch = r.groupby(["acquisition_channel", "months_since_start"]).agg(obs=("customers_observed", "sum"), ret=("customers_retained", "sum"), rev=("net_revenue_usd", "sum")).reset_index()
    ch["retention"] = M.retention_rate(ch.ret, ch.obs)
    ch["revenue_per_customer"] = M.safe_divide(ch.rev, ch.obs)
    ch["cumulative_revenue_per_customer"] = ch.sort_values("months_since_start").groupby("acquisition_channel").revenue_per_customer.cumsum()
    ch = ch[ch.obs >= 30]
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(px.line(ch, x="months_since_start", y="retention", color="acquisition_channel", title="Retention curve by acquisition channel", labels={"months_since_start": "months since first payment"}), width="stretch")
    with c2:
        st.plotly_chart(px.line(ch, x="months_since_start", y="cumulative_revenue_per_customer", color="acquisition_channel", title="Cumulative net revenue per customer (USD)", labels={"months_since_start": "months since first payment", "cumulative_revenue_per_customer": "USD"}), width="stretch")
    st.subheader("Cohort revenue")
    cr = cohort.assign(cohort=cohort.cohort_month.dt.strftime("%Y-%m")).pivot(index="cohort", columns="months_since_start", values="rev").round(0)
    st.dataframe(cr, width="stretch")
    ui.download(cohort.assign(cohort_month=cohort.cohort_month.dt.strftime("%Y-%m")), "cohort_retention")
    ui.definition("Retention", "retention(k) = customers who made a payment in billing cycle k / customers observable at k. Churn = 1 - retention. Revenue is net of refunds, dated by payment.")
