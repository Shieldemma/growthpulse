import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from growthpulse import experiment as E


def make_df(n, p0, lift, seed=0, exposed_t=1.0, exposed_c=0.0):
    rng = np.random.default_rng(seed)
    g = np.where(rng.random(n) < 0.5, "treatment", "control")
    exp = np.where(g == "treatment", rng.random(n) < exposed_t, rng.random(n) < exposed_c).astype(int)
    conv = (rng.random(n) < p0 * (1 + lift * exp)).astype(int)
    return pd.DataFrame({"assigned_group": g, "was_exposed": exp, "converted": conv, "revenue_usd": conv * 100.0,
                         "device_category": rng.choice(["desktop", "mobile"], n), "prior_sessions": rng.poisson(2, n)})


def test_ztest_matches_scipy_chi2():
    z, p = E.two_proportion_ztest(120, 1000, 90, 1000)
    chi2 = stats.chi2_contingency([[120, 880], [90, 910]], correction=False)
    assert p == pytest.approx(chi2[1], rel=1e-6)
    assert z > 0


def test_ztest_handles_degenerate():
    assert math.isnan(E.two_proportion_ztest(0, 100, 0, 100)[0])
    assert math.isnan(E.two_proportion_ztest(1, 0, 1, 10)[0])


def test_ci_contains_estimate_and_zero_when_null():
    lo, hi = E.newcombe_diff_ci(50, 1000, 50, 1000)
    assert lo < 0 < hi


def test_relative_lift_ci_nan_when_zero_conversions():
    assert all(math.isnan(v) for v in E.relative_lift_ci(0, 100, 5, 100))


def test_power_functions_are_consistent():
    n = E.required_sample_size_per_arm(0.02, 0.20)
    assert E.achieved_power(0.02, 0.20, n) == pytest.approx(0.8, abs=0.01)
    assert E.minimum_detectable_effect(0.02, n) == pytest.approx(0.20, abs=0.01)
    assert E.required_sample_size_per_arm(0.02, 0.10) > n          # smaller effect needs more users


def test_srm_detects_broken_randomisation():
    assert E.srm_check(5000, 5000)["ok"]
    assert not E.srm_check(5600, 4400)["ok"]


def test_analysis_recovers_known_effect():
    df = make_df(400_000, 0.02, 0.25, seed=1)
    r = E.analyze_experiment(df, spend_usd=10_000, attributed_revenue_usd=20_000)
    assert r.significant and r.rel_lift_ci_low < 0.25 < r.rel_lift_ci_high
    assert r.abs_lift_ci_low < 0.005 < r.abs_lift_ci_high
    assert r.cace_rel_lift == pytest.approx(0.25, abs=0.06)


def test_analysis_does_not_invent_effect_under_null():
    df = make_df(100_000, 0.02, 0.0, seed=5)
    r = E.analyze_experiment(df, 1000, 5000)
    assert not r.significant and r.rel_lift_ci_low < 0 < r.rel_lift_ci_high
    assert "Inconclusive" in r.verdict


def test_false_positive_rate_is_near_alpha():
    hits = sum(E.analyze_experiment(make_df(20_000, 0.03, 0.0, seed=s), 1, 1).significant for s in range(150))
    assert hits / 150 < 0.12


def test_incremental_roas_vs_attributed():
    df = make_df(200_000, 0.02, 0.0, seed=9, exposed_t=0.9)
    r = E.analyze_experiment(df, spend_usd=5000, attributed_revenue_usd=15_000)
    assert r.attributed_roas == 3.0 and abs(r.incremental_roas) < 1.5


def test_invalid_experiment_flagged_when_srm_fails():
    df = make_df(10_000, 0.02, 0.1, seed=2)
    df = pd.concat([df[df.assigned_group == "treatment"], df[df.assigned_group == "control"].iloc[:3000]])
    assert "INVALID" in E.analyze_experiment(df, 1, 1).verdict


def test_balance_check_runs_and_flags_nothing_when_randomised():
    b = E.covariate_balance(make_df(20_000, 0.03, 0.0, seed=4))
    assert b.balanced.all()
