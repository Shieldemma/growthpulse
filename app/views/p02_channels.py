import plotly.express as px
import streamlit as st

from growthpulse import metrics as M
from lib import data, filters, ui


def render():
    data.require_data()
    ui.header("Marketing Channel Performance", "Efficiency and customer quality by channel and campaign.")
    f = filters.sidebar()
    df = filters.apply(data.perf(f.model), f)
    if df.empty:
        return ui.empty_state()
    ch = M.aggregate_performance(df, by=["channel_name"], window=f.window, gross_margin=f.gross_margin, data_end=f.data_end)
    paid = ch[ch.spend_usd > 0]
    ui.kpis([("Total spend", ui.fmt_usd(ch.spend_usd.sum()), None), ("Paid channels", str(len(paid)), None),
             ("Best ROAS", f"{paid.loc[paid.roas_window.idxmax(), 'channel_name']} ({ui.fmt_num(paid.roas_window.max(), 2)})" if paid.roas_window.notna().any() else "n/a",
              "Highest revenue per ad dollar in the window"),
             ("Lowest CAC", f"{paid.loc[paid.cac.idxmin(), 'channel_name']} ({ui.fmt_usd(paid.cac.min())})" if paid.cac.notna().any() else "n/a", None)])
    c1, c2 = st.columns(2)
    with c1:
        if paid.empty:
            ui.empty_state("No paid spend in the selection.")
        else:
            st.plotly_chart(px.bar(paid.sort_values("cac"), x="channel_name", y="cac", title="Paid-media CAC (USD)", labels={"cac": "USD", "channel_name": ""}), width="stretch")
    with c2:
        if not paid.empty:
            st.plotly_chart(px.bar(paid.sort_values("roas_window"), x="channel_name", y="roas_window", title=f"ROAS ({'3' if f.window=='m3' else '12'}-cycle revenue / spend)",
                                   labels={"roas_window": "ROAS", "channel_name": ""}).add_hline(y=1, line_dash="dot", annotation_text="1.0 = revenue equals spend (not breakeven on profit)"), width="stretch")
    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(px.bar(ch.sort_values("new_customers"), x="new_customers", y="channel_name", orientation="h", title="New paying customers (credited)", labels={"channel_name": "", "new_customers": "customers"}), width="stretch")
    with c4:
        st.plotly_chart(px.bar(ch.sort_values("revenue_per_customer_window"), x="revenue_per_customer_window", y="channel_name", orientation="h",
                               title="Revenue per customer in window (customer quality)", labels={"channel_name": "", "revenue_per_customer_window": "USD"}), width="stretch")
    monthly = df.assign(month=df.metric_date.dt.to_period("M").dt.to_timestamp()).groupby(["month", "channel_name"]).agg(spend=("spend_usd", "sum"), customers=("new_customers", "sum")).reset_index()
    st.plotly_chart(px.area(monthly, x="month", y="customers", color="channel_name", title="New customers by channel over time", labels={"month": "", "customers": "customers"}), width="stretch")
    st.subheader("Channel table")
    show = ch.rename(columns={"cac": "cac_paid_media"})
    st.dataframe(show, width="stretch", hide_index=True, column_config={c: st.column_config.NumberColumn(format="%.2f") for c in show.columns if show[c].dtype == "float64"})
    ui.download(show, "channel_performance")
    st.subheader("Campaign drill-down")
    camp = M.aggregate_performance(df[df.spend_usd >= 0], by=["channel_name", "campaign_id"], window=f.window, gross_margin=f.gross_margin, data_end=f.data_end)
    camp = camp[camp.spend_usd > 0]
    if camp.empty:
        ui.empty_state("No paid campaigns in the selection.")
    else:
        st.dataframe(camp, width="stretch", hide_index=True)
        ui.download(camp, "campaign_performance")
    ui.definition("channel metrics", "**CPC** = spend / clicks. **CAC (paid media)** = spend / new paying customers. **ROAS** = net revenue in the window / spend. "
                  "Customers are credited with the sidebar attribution model. Zero denominators show *n/a*, never 0. ROAS is not profit and does not prove the ads caused sales (see Incrementality).")
