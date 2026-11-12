"""Business metric functions (pure, unit-tested). Used by the dashboard, the report and the tests.

Rules shared by every function:
  * a zero, negative or missing denominator returns NaN (never a fake 0 and never an exception),
  * NaN inputs propagate as NaN,
  * all functions work on scalars and on pandas Series / numpy arrays.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

NAN = float("nan")


def safe_divide(numerator, denominator):
    """numerator / denominator, NaN where the denominator is 0/NaN/None or the numerator is missing.
    Works on scalars (returns float) and on Series/arrays (returns Series/array)."""
    if np.isscalar(numerator) and np.isscalar(denominator) or numerator is None or denominator is None:
        try:
            n, d = float(numerator), float(denominator)
        except (TypeError, ValueError):
            return NAN
        if math.isnan(n) or math.isnan(d) or d == 0:
            return NAN
        return n / d
    index = numerator.index if isinstance(numerator, pd.Series) else getattr(denominator, "index", None)
    num = np.asarray(numerator, dtype=float)
    den = np.asarray(denominator, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where((den == 0) | np.isnan(den) | np.isnan(num), np.nan, num / np.where(den == 0, 1.0, den))
    return pd.Series(out, index=index) if index is not None else out


def conversion_rate(conversions, visitors):
    return safe_divide(conversions, visitors)


def cost_per_click(spend, clicks):
    return safe_divide(spend, clicks)


def cost_per_acquisition(spend, conversions):
    return safe_divide(spend, conversions)


def cac(spend, new_customers, overhead=0.0):
    """Customer Acquisition Cost.
    Paid-media CAC:   cac(spend, customers)
    Fully loaded CAC: cac(spend, customers, overhead=allocated non-media costs)
    NaN when no customers were acquired."""
    return safe_divide(spend + overhead, new_customers)


def roas(revenue, spend):
    """Return on ad spend = revenue / spend. NOT profit and NOT proof of incrementality."""
    return safe_divide(revenue, spend)


def arpc(revenue, customers):
    """Average revenue per customer."""
    return safe_divide(revenue, customers)


def ltv_cac_ratio(ltv, cac_value):
    return safe_divide(ltv, cac_value)


def gross_profit(revenue, gross_margin):
    if not 0 <= gross_margin <= 1:
        raise ValueError("gross_margin must be between 0 and 1")
    return revenue * gross_margin


def retention_rate(retained, observed):
    return safe_divide(retained, observed)


def churn_rate(retained, observed):
    r = retention_rate(retained, observed)
    return 1 - r


def monthly_hazard_from_retention(retention_curve: pd.Series, start: int = 3, end: int = 12) -> float:
    """Average monthly churn hazard between months `start` and `end` implied by a retention curve (index = month).
    hazard = 1 - (R_end / R_start) ** (1 / (end - start)). NaN if the curve does not reach `end`."""
    c = retention_curve.dropna()
    if start not in c.index or end not in c.index or c[start] <= 0 or end <= start:
        return NAN
    return float(1 - (c[end] / c[start]) ** (1.0 / (end - start)))


def projected_ltv(monthly_revenue: float, gross_margin: float, monthly_churn: float,
                  horizon_months: int = 36, annual_discount_rate: float = 0.10,
                  observed_revenue_months: float = 0.0, observed_revenue: float = 0.0) -> float:
    """ESTIMATED lifetime value (a model, not an observation).

    Expected gross-profit per acquired customer over `horizon_months`, assuming a constant monthly churn hazard
    after the observed window and discounting at `annual_discount_rate`:
        LTV = sum_{k=0}^{H-1} monthly_revenue * margin * (1 - churn)^k / (1 + r_m)^k
    If an observed window is supplied, observed revenue is used for the first `observed_revenue_months`
    and the model only extends beyond it. Returns NaN for missing/invalid inputs.
    """
    vals = [monthly_revenue, gross_margin, monthly_churn]
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in vals):
        return NAN
    if not (0 <= monthly_churn < 1) or horizon_months <= 0:
        return NAN
    r_m = (1 + annual_discount_rate) ** (1 / 12) - 1
    total = 0.0
    start_k = int(observed_revenue_months)
    if start_k > 0:
        total += observed_revenue * gross_margin
    survival = (1 - monthly_churn) ** start_k
    for k in range(start_k, horizon_months):
        total += monthly_revenue * gross_margin * survival / (1 + r_m) ** k
        survival *= 1 - monthly_churn
    return float(total)


def payback_months(cumulative_gross_profit_per_customer: pd.Series, cac_value: float):
    """First month index at which cumulative gross profit per customer >= CAC (NaN if never within the data).
    Input index = months since acquisition (0,1,2...)."""
    if cac_value is None or (isinstance(cac_value, float) and math.isnan(cac_value)) or cac_value <= 0:
        return NAN
    hit = cumulative_gross_profit_per_customer[cumulative_gross_profit_per_customer >= cac_value]
    return float(hit.index[0] + 1) if len(hit) else NAN   # month 0 payment = end of month 1


def window_cutoff(df: pd.DataFrame, window: str, data_end=None) -> pd.Timestamp:
    """Latest acquisition/spend date whose cohort has been observed for the whole window (m3 -> 3 billing cycles)."""
    months = int(window[1:])
    end = pd.Timestamp(data_end) if data_end is not None else pd.to_datetime(df["metric_date"]).max()
    return end - pd.DateOffset(months=months - 1)


def aggregate_performance(df: pd.DataFrame, by: list[str] | None = None, window: str = "m3",
                          gross_margin: float = 0.8, data_end=None) -> pd.DataFrame:
    """Turn rows of mart_marketing_performance (ONE attribution model) into KPI rows.

    `window` (m3, m12, ...) = revenue from the first N billing cycles. ROAS and window-LTV use only rows dated on or
    before the window cutoff (spend AND customers restricted to the same dates), so young cohorts are not penalised
    for being young. CAC, CPC and totals use every row."""
    cutoff = window_cutoff(df, window, data_end)
    g = df.groupby(by, dropna=False) if by else [(None, df)]
    rows = []
    for key, d in g:
        spend, clicks = d.spend_usd.sum(), d.clicks.sum()
        cust, sign, trials = d.new_customers.sum(), d.signups.sum(), d.trials.sum()
        elig = d[pd.to_datetime(d.metric_date) <= cutoff]
        rev_w = elig[f"net_revenue_{window}"].sum()
        spend_w = elig.spend_usd.sum()
        cust_w = elig.new_customers.sum()
        paid = spend > 0
        row = dict(spend_usd=spend, clicks=clicks, signups=sign, trials=trials, new_customers=cust,
                   cpc=cost_per_click(spend, clicks) if paid else NAN, cac=cac(spend, cust) if paid else NAN,
                   cost_per_signup=cost_per_acquisition(spend, sign) if paid else NAN,
                   revenue_window=rev_w, roas_window=roas(rev_w, spend_w) if spend_w > 0 else NAN,
                   revenue_per_customer_window=arpc(rev_w, cust_w),
                   gp_per_customer_window=arpc(rev_w, cust_w) * gross_margin if cust_w else NAN,
                   net_revenue_to_date=d.net_revenue_to_date.sum())
        row["ltv_cac_window"] = ltv_cac_ratio(row["gp_per_customer_window"], safe_divide(spend_w, cust_w)) if spend_w > 0 else NAN
        if by:
            keys = key if isinstance(key, tuple) else (key,)
            row.update(dict(zip(by, keys)))
        rows.append(row)
    out = pd.DataFrame(rows)
    if by:
        out = out[by + [c for c in out.columns if c not in by]]
    return out
