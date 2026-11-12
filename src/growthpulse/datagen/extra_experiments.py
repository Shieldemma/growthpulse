"""Two more SYNTHETIC experiment types with known truth: a GEO holdout (difference-in-differences) and a LIFECYCLE/CRM
program holdout with short-, mid- and long-term outcomes. Ground truth is returned separately and never loaded to the warehouse."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import assumptions as A

GEO_ID = "GEO-001"
GEO_PRE_DAYS, GEO_TEST_DAYS = 56, 28
GEO_START = pd.Timestamp("2025-07-07")          # Monday; test starts after the 8-week pre-period
LIFE_ID = "LIFE-001"
LIFE_WINDOW = ("2025-03-03", "2025-03-30")


def generate_geo(cfg):
    rng = np.random.default_rng(cfg.seed + 2)
    n_geo = 40
    pop = rng.lognormal(0, 0.6, n_geo)
    pop = pop / pop.mean()
    treated = np.zeros(n_geo, bool)
    treated[rng.choice(n_geo, n_geo // 2, replace=False)] = True
    start = GEO_START - pd.Timedelta(days=GEO_PRE_DAYS)
    days = pd.date_range(start, periods=GEO_PRE_DAYS + GEO_TEST_DAYS, freq="D")
    true_lift, base_daily, cost_per_day_per_pop = 0.09, 6.0, 140.0
    dow = np.array([1.1, 1.1, 1.05, 1.05, 1.0, 0.8, 0.8])[days.dayofweek]
    trend = 1 + 0.002 * np.arange(len(days))
    geo_trend = rng.normal(0, 0.0007, n_geo)             # small geo-specific drift (parallel trends hold only approximately)
    rows = []
    for g in range(n_geo):
        post = (np.arange(len(days)) >= GEO_PRE_DAYS)
        mu = base_daily * pop[g] * dow * trend * (1 + geo_trend[g] * np.arange(len(days)))
        mu = mu * np.where(treated[g] & post, 1 + true_lift, 1.0)
        conv = rng.poisson(mu * rng.lognormal(0, 0.05, len(days)))
        rev = np.round(conv * rng.normal(140, 12, len(days)).clip(60), 2)
        spend = np.where(treated[g] & post, cost_per_day_per_pop * pop[g] * dow, 0.0).round(2)
        rows.append(pd.DataFrame({"geo_id": f"geo_{g + 1:02d}", "activity_date": days.date, "assigned_group":
                                  "treatment" if treated[g] else "control", "population_index": round(pop[g], 4),
                                  "spend_usd": spend, "conversions": conv, "revenue_usd": rev}))
    outcomes = pd.concat(rows, ignore_index=True)
    catalog = pd.DataFrame([{
        "experiment_id": GEO_ID, "experiment_name": "Paid search non-brand geo holdout",
        "hypothesis": "Switching on non-brand paid search in treatment geos increases daily paid conversions vs. control geos (difference-in-differences).",
        "channel_id": "ch_paid_search", "pre_start_date": start.date(), "test_start_date": GEO_START.date(),
        "test_end_date": days[-1].date(), "n_geos": n_geo}])
    truth = {"true_relative_lift": true_lift, "n_geos": n_geo, "design": "campaign OFF in all geos pre-period; ON in treatment geos only during test"}
    return catalog, outcomes, truth


def generate_lifecycle(cfg):
    """Trial-onboarding email series (CRM lifecycle program) vs a 10% holdout-style 50/50 test."""
    rng = np.random.default_rng(cfg.seed + 3)
    n = int(30000 * min(1.0, max(cfg.scale, 0.25)))
    p0, lift = 0.30, 0.08
    group = np.where(rng.random(n) < 0.5, "treatment", "control")
    device = rng.choice(["desktop", "mobile", "tablet"], size=n, p=[0.62, 0.32, 0.06])
    plan_ids = [x[0] for x in A.PLANS]
    price_map = {x[0]: x[2] for x in A.PLANS}
    plan = rng.choice(plan_ids, size=n, p=[0.5, 0.38, 0.12])
    price = np.array([price_map[p] for p in plan])
    p_paid = np.where(group == "treatment", p0 * (1 + lift), p0)
    paid = rng.random(n) < p_paid
    inc_share = (p0 * lift) / (p0 * (1 + lift))      # share of treated payers who would NOT have paid without the program
    is_incremental = paid & (group == "treatment") & (rng.random(n) < inc_share)
    hazard = np.where(is_incremental, 0.12, 0.05)    # incremental payers churn faster (lower quality)
    cycles = np.ones(n, int)
    alive = paid.copy()
    for _ in range(5):
        alive = alive & (rng.random(n) > hazard)
        cycles += alive
    cycles = np.where(paid, cycles, 0)
    cost_per_user = 0.35                              # email platform + content cost per treated user
    start, end = pd.Timestamp(LIFE_WINDOW[0]), pd.Timestamp(LIFE_WINDOW[1])
    users = pd.DataFrame({
        "experiment_id": LIFE_ID, "unit_id": [f"L-{i:06d}" for i in range(1, n + 1)], "assigned_group": group,
        "assignment_date": (start + pd.to_timedelta(rng.integers(0, (end - start).days + 1, n), unit="D")).date,
        "device_category": device, "plan_id": plan, "paid_30d": paid.astype(int),
        "active_90d": (cycles >= 3).astype(int), "active_180d": (cycles >= 6).astype(int),
        "revenue_30d": np.where(cycles >= 1, price, 0.0), "revenue_90d": price * np.minimum(cycles, 3),
        "revenue_180d": price * np.minimum(cycles, 6)})
    n_t = int((group == "treatment").sum())
    catalog = pd.DataFrame([{
        "experiment_id": LIFE_ID, "experiment_name": "Trial onboarding email series (lifecycle)",
        "hypothesis": "A 5-email onboarding series for trial users increases paid conversion within 30 days and its value persists to 90 and 180 days.",
        "start_date": start.date(), "end_date": end.date(), "program_cost_usd": round(n_t * cost_per_user, 2), "planned_alpha": 0.05}])
    truth = {"true_relative_lift_in_paid_conversion": lift, "baseline_paid_30d": p0,
             "incremental_payers_monthly_churn": 0.12, "regular_payers_monthly_churn": 0.05,
             "note": "incremental payers are lower quality, so the revenue lift decays at longer horizons"}
    return catalog, users, truth
