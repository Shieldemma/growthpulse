"""Shared UI helpers."""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from . import data


def banner():
    st.warning("**SYNTHETIC DATA** - the SaaS, marketing and experiment data are simulated (fixed seed). "
               "Results demonstrate methods; they are not evidence about a real company.", icon="🧪")


def header(title: str, subtitle: str = ""):
    st.title(title)
    if subtitle:
        st.caption(subtitle)
    banner()


def fmt_usd(x, d=0):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"-${abs(x):,.{d}f}" if x < 0 else f"${x:,.{d}f}"


def fmt_num(x, d=0):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:,.{d}f}"


def fmt_pct(x, d=1):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}%}"


def kpis(items: list[tuple[str, str, str | None]]):
    cols = st.columns(len(items))
    for c, (label, value, help_) in zip(cols, items):
        c.metric(label, value, help=help_)


def empty_state(msg: str = "No data for the selected filters.", hint: str = "Widen the date range or select more channels/campaigns."):
    st.info(f"**{msg}** {hint}")


def download(df: pd.DataFrame, name: str, label: str = "Download table (CSV)"):
    st.download_button(label, df.to_csv(index=False).encode(), file_name=f"{name}.csv", mime="text/csv", key=f"dl_{name}")


def definition(title: str, body: str):
    with st.expander(f"Definition - {title}"):
        st.markdown(body)
