"""Reference (pure pandas) implementation of the rule-based attribution models.

The production calculation is SQL (dbt model int_attribution_credit). This independent implementation is used to
TEST the SQL: tests build the same journeys, run both, and compare credit. Rule-based attribution describes how
credit is SHARED across touches - it never proves that a channel CAUSED a conversion (see experiment.py).
"""
from __future__ import annotations

import pandas as pd

MODELS = ["first_touch", "last_touch", "linear", "position_based"]


def credit_for_journey(n_touches: int, model: str) -> list[float]:
    """Credit per touch (in order) for one converting customer. Always sums to 1."""
    if n_touches < 1:
        raise ValueError("a converting customer needs at least one touch")
    if model == "first_touch":
        return [1.0] + [0.0] * (n_touches - 1)
    if model == "last_touch":
        return [0.0] * (n_touches - 1) + [1.0]
    if model == "linear":
        return [1.0 / n_touches] * n_touches
    if model == "position_based":
        if n_touches == 1:
            return [1.0]
        if n_touches == 2:
            return [0.5, 0.5]
        mid = 0.2 / (n_touches - 2)
        return [0.4] + [mid] * (n_touches - 2) + [0.4]
    raise ValueError(f"unknown attribution model: {model}")


def attribute(touchpoints: pd.DataFrame, model: str) -> pd.DataFrame:
    """touchpoints columns: customer_id, session_ts, channel_name (any order). Returns one row per touch with `credit`."""
    t = touchpoints.sort_values(["customer_id", "session_ts"]).reset_index(drop=True).copy()
    t["credit"] = 0.0
    for _, idx in t.groupby("customer_id").groups.items():
        t.loc[idx, "credit"] = credit_for_journey(len(idx), model)
    return t


def channel_credit(touchpoints: pd.DataFrame, model: str, value: pd.Series | None = None) -> pd.Series:
    """Total credit (or credit x per-customer value, indexed by customer_id) by channel."""
    t = attribute(touchpoints, model)
    if value is not None:
        t["credit"] = t["credit"] * t["customer_id"].map(value).fillna(0.0)
    return t.groupby("channel_name")["credit"].sum().sort_values(ascending=False)
