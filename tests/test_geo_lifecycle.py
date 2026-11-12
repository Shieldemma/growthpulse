import numpy as np
import pandas as pd
import pytest

from growthpulse import analytics, geo_lift, lifecycle
from growthpulse.datagen import GenConfig
from growthpulse.datagen.extra_experiments import generate_geo, generate_lifecycle


def test_geo_lift_recovers_known_effect_and_placebo_is_null():
    cat, out, truth = generate_geo(GenConfig(seed=5))
    res, weekly = geo_lift.analyze_geo_lift(out, cat.iloc[0])
    r = res.iloc[0]
    assert r.rel_lift_ci_low < truth["true_relative_lift"] < r.rel_lift_ci_high
    assert r.significant and r.p_value_randomisation < 0.05
    assert "placebo_pre_period_tau" in res.columns and 0 <= r.placebo_p_value <= 1                # the diagnostic is always reported
    assert len(weekly) > 0 and {"treatment", "control"} == set(weekly.assigned_group)


def test_geo_lift_default_seed_has_small_placebo():
    cat, out, _ = generate_geo(GenConfig(seed=42))
    r = geo_lift.analyze_geo_lift(out, cat.iloc[0])[0].iloc[0]
    assert abs(r.placebo_pre_period_tau) < 0.5 * abs(r.tau_conversions_per_geo_day) and r.parallel_trends_ok


def test_geo_lift_no_effect_is_not_significant():
    cat, out, _ = generate_geo(GenConfig(seed=9))
    out = out.copy()
    post = pd.to_datetime(out.activity_date) >= pd.Timestamp(cat.iloc[0].test_start_date)
    treated_post = (out.assigned_group == "treatment") & post
    out.loc[treated_post, "conversions"] = (out.loc[treated_post, "conversions"] / 1.09).round().astype(int)   # remove the built-in lift
    res, _ = geo_lift.analyze_geo_lift(out, cat.iloc[0])
    assert abs(res.iloc[0].rel_lift) < 0.06


def test_geo_assignment_is_per_geo_and_pre_period_has_no_spend():
    cat, out, _ = generate_geo(GenConfig(seed=5))
    assert out.groupby("geo_id").assigned_group.nunique().max() == 1
    pre = pd.to_datetime(out.activity_date) < pd.Timestamp(cat.iloc[0].test_start_date)
    assert out[pre].spend_usd.sum() == 0 and out[(out.assigned_group == "control")].spend_usd.sum() == 0


def test_lifecycle_shows_conversion_lift_that_decays_in_value():
    cat, users, truth = generate_lifecycle(GenConfig(seed=5))
    out, val = lifecycle.analyze_lifecycle(users, cat.iloc[0])
    r30 = out[out.metric == "Paid conversion (30d)"].iloc[0]
    assert r30.significant and r30.rel_ci_low < truth["true_relative_lift_in_paid_conversion"] < r30.rel_ci_high
    rev = out[out.kind == "per_user_usd"].set_index("horizon_days")
    assert rev.loc[180, "rel_lift"] < rev.loc[30, "rel_lift"]          # incremental customers retain worse
    assert len(val) == 3 and (val.program_cost_per_treated_user > 0).all()


def test_lifecycle_group_balance_and_randomisation():
    _, users, _ = generate_lifecycle(GenConfig(seed=5))
    assert 0.47 < (users.assigned_group == "treatment").mean() < 0.53
    assert users.unit_id.is_unique


def test_calibration_flags_disagreement_and_bounds_factor():
    exp = pd.DataFrame([{"experiment_id": "E1", "channel_id": "ch_display", "incremental_roas": 0.1, "significant": False}])
    geo = pd.DataFrame([{"experiment_id": "G1", "incremental_roas": 3.0, "significant": True}])
    mmm = pd.DataFrame([{"channel": "display", "avg_roi": 1.0, "avg_roi_p05": 0.6, "avg_roi_p95": 1.4},
                        {"channel": "paid_search", "avg_roi": 1.0, "avg_roi_p05": 0.6, "avg_roi_p95": 1.4}])
    cal = analytics.calibration_table(exp, geo, mmm).set_index("experiment_id")
    assert not cal.loc["E1", "experiment_inside_mmm_interval"] and "over-states" in cal.loc["E1", "reading"]
    assert cal.loc["G1", "calibration_factor"] == pytest.approx(3.0) and "under-states" in cal.loc["G1", "reading"]
    assert 0.25 <= cal.loc["E1", "calibration_factor"] <= 4.0


@pytest.mark.slow
def test_insights_brief_is_deterministic_and_guarded(quick_pipeline):
    import duckdb
    from growthpulse import insights
    con = duckdb.connect(str(quick_pipeline["db"]), read_only=True)
    f1, f2 = insights.build_facts(con), insights.build_facts(con)
    assert f1 == f2
    brief, prompt = insights.render_brief(f1), insights.render_llm_prompt(f1)
    assert "SYNTHETIC" in brief and "ONLY the numbers" in prompt and "verify" in prompt
    assert (quick_pipeline["dir"] / "weekly_insight_brief.md").exists()
