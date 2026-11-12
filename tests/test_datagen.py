import hashlib

import numpy as np
import pandas as pd
import pytest

from growthpulse.datagen import GenConfig, generate, write_dataset
from growthpulse.datagen.generator import add_months
from growthpulse.datagen import schema


def test_schema_matches_generated_tables(quick_tables):
    for t in schema.TABLES:
        assert set(schema.columns(t)) <= set(quick_tables[t].columns), t
        assert len(quick_tables[t]) > 0, t


def test_same_seed_is_byte_identical(tmp_path):
    cfg = GenConfig(seed=3, scale=0.05)
    a = write_dataset(generate(cfg), tmp_path / "a", cfg)
    b = write_dataset(generate(cfg), tmp_path / "b", cfg)
    assert {k: v["sha256"] for k, v in a["tables"].items()} == {k: v["sha256"] for k, v in b["tables"].items()}


def test_different_seed_differs(tmp_path):
    a = write_dataset(generate(GenConfig(seed=3, scale=0.05)), tmp_path / "a", GenConfig(seed=3, scale=0.05))
    b = write_dataset(generate(GenConfig(seed=4, scale=0.05)), tmp_path / "b", GenConfig(seed=4, scale=0.05))
    assert a["tables"]["payments"]["sha256"] != b["tables"]["payments"]["sha256"]


def test_primary_keys_unique(quick_tables):
    for t, k in [("sessions", "session_id"), ("customers", "customer_id"), ("subscriptions", "subscription_id"),
                 ("payments", "payment_id"), ("refunds", "refund_id"), ("events", "event_id"), ("campaigns", "campaign_id")]:
        assert quick_tables[t][k].is_unique, t
    assert not quick_tables["ad_spend_daily"].duplicated(["spend_date", "campaign_id"]).any()


def test_referential_integrity(quick_tables):
    T = quick_tables
    assert set(T["sessions"].channel_id) <= set(T["channels"].channel_id)
    assert set(T["sessions"].campaign_id.dropna()) <= set(T["campaigns"].campaign_id)
    assert set(T["events"].session_id) <= set(T["sessions"].session_id)
    assert set(T["customers"].visitor_id) <= set(T["sessions"].visitor_id)
    assert set(T["subscriptions"].customer_id) <= set(T["customers"].customer_id)
    assert set(T["payments"].subscription_id) <= set(T["subscriptions"].subscription_id)
    assert set(T["refunds"].payment_id) <= set(T["payments"].payment_id)
    assert set(T["subscriptions"].plan_id) <= set(T["plans"].plan_id)


def test_media_numbers_are_sane(quick_tables):
    a = quick_tables["ad_spend_daily"]
    assert (a.spend_usd >= 0).all() and (a.clicks <= a.impressions).all()
    sessions = quick_tables["sessions"].dropna(subset=["campaign_id"])
    sessions = sessions.assign(d=pd.to_datetime(sessions.session_ts).dt.date).groupby(["d", "campaign_id"]).size().rename("s").reset_index()
    j = sessions.merge(a.rename(columns={"spend_date": "d"}).assign(d=lambda x: pd.to_datetime(x.d).dt.date), on=["d", "campaign_id"])
    assert (j.s <= j.clicks).all()


def test_paid_sessions_only_have_campaigns(quick_tables):
    s = quick_tables["sessions"]
    paid = s.channel_id.isin(["ch_paid_search", "ch_paid_social", "ch_display", "ch_affiliate"])
    first = s.sort_values("session_ts").groupby("visitor_id").head(1)
    assert first[first.channel_id.isin(["ch_paid_search", "ch_paid_social", "ch_display", "ch_affiliate"])].campaign_id.notna().all()
    assert s[~paid].campaign_id.isna().all()


def test_funnel_event_ordering_and_logic(quick_tables):
    ev = quick_tables["events"].merge(quick_tables["sessions"][["session_id", "session_ts"]], on="session_id")
    assert (pd.to_datetime(ev.event_ts) >= pd.to_datetime(ev.session_ts)).all()
    c = quick_tables["customers"]
    sc = ev[ev.event_name == "signup_complete"]
    assert len(sc) == len(c)
    # every trial/signup_complete has a customer id; every signup_complete also viewed pricing in the same session
    assert ev[ev.event_name.isin(["signup_complete", "trial_start"])].customer_id.notna().all()
    pr = set(ev[ev.event_name == "view_pricing"].session_id)
    assert set(sc.session_id) <= pr


def test_payments_follow_subscription_rules(quick_tables):
    T = quick_tables
    p = T["payments"].merge(T["subscriptions"], on="subscription_id", suffixes=("", "_s"))
    assert (pd.to_datetime(p.payment_date) >= pd.to_datetime(p.start_date)).all()
    ended = p[p.end_date.notna()]
    assert (pd.to_datetime(ended.payment_date) < pd.to_datetime(ended.end_date)).all()
    assert (pd.to_datetime(p.payment_date) <= pd.Timestamp("2025-12-28")).all()
    first = p[p.billing_cycle_number == 0]
    assert first.subscription_id.is_unique and len(first) == len(T["subscriptions"])
    prices = T["plans"].set_index("plan_id").monthly_price_usd
    assert (p.gross_amount_usd <= p.plan_id.map(prices) + 0.01).all()


def test_refunds_never_exceed_payments_or_precede_them(quick_tables):
    r = quick_tables["refunds"].merge(quick_tables["payments"], on="payment_id")
    assert (r.refund_amount_usd <= r.gross_amount_usd + 0.01).all()
    assert (pd.to_datetime(r.refund_date) >= pd.to_datetime(r.payment_date)).all()
    assert quick_tables["refunds"].payment_id.is_unique


def test_revenue_reconciles(quick_tables):
    p, r = quick_tables["payments"], quick_tables["refunds"]
    assert p.gross_amount_usd.sum() - r.refund_amount_usd.sum() > 0


def test_weekly_history_is_36_months(quick_tables):
    d = pd.to_datetime(quick_tables["ad_spend_daily"].spend_date)
    assert (d.max() - d.min()).days + 1 == 1092   # 156 weeks


def test_experiment_data_shape(quick_tables):
    a = quick_tables["experiment_assignments"]
    for _, g in a.groupby("experiment_id"):
        assert set(g.assigned_group) == {"treatment", "control"}
        assert 0.45 < (g.assigned_group == "treatment").mean() < 0.55
    # control exposure is only contamination; treatment exposure is the norm
    assert a[a.assigned_group == "treatment"].was_exposed.mean() > 0.9
    assert a[a.assigned_group == "control"].was_exposed.mean() < 0.05
    assert (a.revenue_usd[a.converted == 0] == 0).all()


def test_add_months_clips_day():
    out = add_months(np.array(["2024-01-31", "2023-03-31"], dtype="datetime64[D]"), np.array([1, 1]))
    assert str(out[0]) == "2024-02-29" and str(out[1]) == "2023-04-30"
