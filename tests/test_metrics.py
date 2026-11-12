import math

import numpy as np
import pandas as pd
import pytest

from growthpulse import metrics as M


def test_cac_basic_and_loaded():
    assert M.cac(1000, 10) == 100
    assert M.cac(1000, 10, overhead=500) == 150


@pytest.mark.parametrize("fn,args", [(M.cac, (100, 0)), (M.roas, (100, 0)), (M.conversion_rate, (5, 0)),
                                     (M.cost_per_click, (50, 0)), (M.arpc, (10, 0)), (M.ltv_cac_ratio, (3, 0))])
def test_zero_denominator_returns_nan_not_error_or_zero(fn, args):
    assert math.isnan(fn(*args))


def test_missing_values_propagate_as_nan():
    assert math.isnan(M.roas(None, 10))
    assert math.isnan(M.roas(float("nan"), 10))
    assert math.isnan(M.cac(100, float("nan")))


def test_series_division_is_elementwise_and_safe():
    out = M.safe_divide(pd.Series([10, 5, 3]), pd.Series([2, 0, np.nan]))
    assert out.iloc[0] == 5 and math.isnan(out.iloc[1]) and math.isnan(out.iloc[2])


def test_roas_not_profit():
    assert M.roas(300, 100) == 3.0   # revenue per ad dollar, regardless of margin


def test_retention_and_churn():
    assert M.retention_rate(60, 100) == 0.6
    assert M.churn_rate(60, 100) == pytest.approx(0.4)
    assert math.isnan(M.retention_rate(0, 0))


def test_gross_profit_validates_margin():
    assert M.gross_profit(100, 0.8) == 80
    with pytest.raises(ValueError):
        M.gross_profit(100, 1.5)


def test_projected_ltv_known_values():
    # no churn, no discount, 12 months: revenue*margin*12
    assert M.projected_ltv(100, 0.5, 0.0, horizon_months=12, annual_discount_rate=0.0) == pytest.approx(600)
    # churn lowers LTV; invalid churn -> NaN
    assert M.projected_ltv(100, 0.5, 0.1, 12, 0.0) < 600
    assert math.isnan(M.projected_ltv(100, 0.5, 1.0))
    assert math.isnan(M.projected_ltv(float("nan"), 0.5, 0.1))
    # geometric series closed form
    expected = 100 * 0.8 * (1 - 0.9 ** 36) / (1 - 0.9)
    assert M.projected_ltv(100, 0.8, 0.1, 36, 0.0) == pytest.approx(expected)


def test_observed_window_is_used_then_model_extends():
    v = M.projected_ltv(100, 1.0, 0.0, horizon_months=24, annual_discount_rate=0.0, observed_revenue_months=12, observed_revenue=1000)
    assert v == pytest.approx(1000 + 12 * 100)


def test_hazard_from_retention():
    c = pd.Series({3: 0.8, 12: 0.8 * 0.95 ** 9})
    assert M.monthly_hazard_from_retention(c) == pytest.approx(0.05)
    assert math.isnan(M.monthly_hazard_from_retention(pd.Series({3: 0.8})))


def test_payback_months():
    cum = pd.Series([20, 45, 70, 95], index=[0, 1, 2, 3])
    assert M.payback_months(cum, 60) == 3.0
    assert math.isnan(M.payback_months(cum, 500))
    assert math.isnan(M.payback_months(cum, float("nan")))


def _perf_rows():
    d = pd.date_range("2025-01-01", periods=400, freq="D")
    return pd.DataFrame({"metric_date": d, "channel_name": "paid_search", "spend_usd": 100.0, "clicks": 10, "signups": 1.0,
                         "trials": 1.0, "new_customers": 0.5, "net_revenue_m3": 60.0, "net_revenue_m12": 150.0, "net_revenue_to_date": 150.0})


def test_aggregate_performance_excludes_young_cohorts_from_roas_but_not_cac():
    df = _perf_rows()
    out = M.aggregate_performance(df, window="m12", gross_margin=0.8).iloc[0]
    assert out.cac == pytest.approx(200.0)                      # every row used
    cutoff = df.metric_date.max() - pd.DateOffset(months=11)
    elig = df[df.metric_date <= cutoff]
    assert out.roas_window == pytest.approx(elig.net_revenue_m12.sum() / elig.spend_usd.sum())
    assert out.revenue_per_customer_window == pytest.approx(300.0)


def test_aggregate_handles_unpaid_channel():
    df = _perf_rows().assign(spend_usd=0.0)
    out = M.aggregate_performance(df, window="m3").iloc[0]
    assert math.isnan(out.cac) and math.isnan(out.roas_window)
