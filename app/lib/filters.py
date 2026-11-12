"""Sidebar filters shared by every page. They genuinely change what each page computes."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from . import data

MODELS = {"first_touch": "First touch", "last_touch": "Last touch", "linear": "Linear (multi-touch)",
          "position_based": "Position-based 40/20/40 (multi-touch)"}


@dataclass
class Filters:
    start: pd.Timestamp
    end: pd.Timestamp
    channels: list[str]
    campaigns: list[str]
    model: str
    window: str
    gross_margin: float
    data_end: pd.Timestamp


def sidebar(show_model: bool = True, show_window: bool = True) -> Filters:
    full = data.perf("first_touch")
    lo, hi = full.metric_date.min().date(), full.metric_date.max().date()
    st.sidebar.header("Filters")
    dr = st.sidebar.date_input("Date range", (lo, hi), min_value=lo, max_value=hi, key="f_dates")
    start, end = (dr[0], dr[1]) if isinstance(dr, (tuple, list)) and len(dr) == 2 else (lo, hi)
    channels = sorted(full.channel_name.unique())
    sel_ch = st.sidebar.multiselect("Channels", channels, default=channels, key="f_channels")
    camps = sorted(full[full.channel_name.isin(sel_ch)].campaign_id.unique())
    sel_camp = st.sidebar.multiselect("Campaigns", camps, default=camps, key="f_campaigns",
                                      help="'none' = sessions/customers that did not come from a paid campaign.")
    model = "first_touch"
    if show_model:
        model = st.sidebar.selectbox("Attribution model", list(MODELS), format_func=MODELS.get, key="f_model",
                                     help="How customers are credited to channels. Rule-based credit, not causal proof.")
    window = "m3"
    if show_window:
        window = st.sidebar.radio("Revenue window for ROAS / LTV", ["m3", "m12"], index=1, key="f_window",
                                  format_func=lambda x: {"m3": "First 3 billing cycles", "m12": "First 12 billing cycles"}[x],
                                  help="Only cohorts observed for the full window are used, to avoid right-censoring bias.")
    gm = st.sidebar.slider("Gross margin assumption", 0.3, 0.95, float(data.meta().get("gross_margin_assumption", 0.8)), 0.01,
                           key="f_gm", help="ASSUMPTION used to turn revenue into gross profit.")
    st.sidebar.caption("Synthetic data. Filters apply to this page's calculations.")
    return Filters(pd.Timestamp(start), pd.Timestamp(end), sel_ch, sel_camp, model, window, gm, full.metric_date.max())


def apply(df: pd.DataFrame, f: Filters, date_col: str = "metric_date", channel_col: str = "channel_name",
          campaign_col: str | None = "campaign_id") -> pd.DataFrame:
    m = (df[date_col] >= f.start) & (df[date_col] <= f.end) & df[channel_col].isin(f.channels)
    if campaign_col and campaign_col in df:
        m &= df[campaign_col].isin(f.campaigns)
    return df[m]
