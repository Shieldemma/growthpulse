"""Synthetic treatment/control experiments with KNOWN true effects.

The true parameters are returned separately (the 'ground truth') and are
never loaded into the warehouse - the analysis code must recover them from
the observed rows, which is how we test the analysis.

Data-generating process for each unit i:
    assigned_group ~ Bernoulli(0.5)               (randomised)
    exposed_i      ~ Bernoulli(1 - treat_not_exposed)   if treatment
                   ~ Bernoulli(control_exposed)          if control (contamination)
    p_i  = p0 * covariate_effect_i * (1 + L * exposed_i)    L = true relative lift among the exposed
    converted_i ~ Bernoulli(p_i)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import assumptions as A

COST_PER_EXPOSED_USER = {"paid_social": 2.10, "display": 0.95, "affiliate": 1.60, "paid_search": 3.0}
WINDOWS = {
    "EXP-001": ("2025-06-02", "2025-06-29"),
    "EXP-002": ("2025-08-04", "2025-08-31"),
    "EXP-003": ("2025-10-06", "2025-10-19"),
}
HYPOTHESES = {
    "EXP-001": "Showing paid-social lookalike ads to eligible visitors increases 14-day paid conversion vs. a randomised holdout.",
    "EXP-002": "Showing display prospecting ads to eligible visitors increases 14-day paid conversion vs. a randomised holdout.",
    "EXP-003": "Affiliate coupon placements increase 14-day paid conversion vs. a randomised holdout (small pilot).",
}


def generate_experiments(cfg):
    rng = np.random.default_rng(cfg.seed + 1)
    cat_rows, frames, truth = [], [], {}
    size_factor = min(1.0, max(cfg.scale, 0.25))
    for exp_id, name, channel, n, p0, lift, ctrl_exposed, treat_miss in cfg.experiments:
        n = int(n * size_factor)
        start, end = pd.Timestamp(WINDOWS[exp_id][0]), pd.Timestamp(WINDOWS[exp_id][1])
        span = (end - start).days + 1
        group = np.where(rng.random(n) < 0.5, "treatment", "control")
        device = rng.choice(["desktop", "mobile", "tablet"], size=n, p=[0.62, 0.32, 0.06])
        prior = rng.poisson(1.8, size=n)
        exposed = np.where(group == "treatment", rng.random(n) >= treat_miss, rng.random(n) < ctrl_exposed).astype(int)
        cov = (1 + 0.10 * (prior - 1.8)) * np.where(device == "desktop", 1.1, np.where(device == "mobile", 0.8, 1.0))
        cov = np.clip(cov, 0.3, None)
        cov = cov / cov.mean()
        p = np.clip(p0 * cov * (1 + lift * exposed), 0, 1)
        conv = (rng.random(n) < p).astype(int)
        plan_ids = [x[0] for x in A.PLANS]
        price = {x[0]: x[2] for x in A.PLANS}
        plan = rng.choice(plan_ids, size=n, p=A.PLAN_MIX[channel])
        revenue = np.where(conv == 1, [price[q] for q in plan], 0.0)
        frames.append(pd.DataFrame({
            "experiment_id": exp_id, "unit_id": [f"{exp_id[-3:]}-{i:06d}" for i in range(1, n + 1)],
            "assigned_group": group,
            "assignment_date": (start + pd.to_timedelta(rng.integers(0, span, size=n), unit="D")).date,
            "device_category": device, "prior_sessions": prior, "was_exposed": exposed,
            "converted": conv, "revenue_usd": revenue}))
        n_exposed_treat = int(((group == "treatment") & (exposed == 1)).sum())
        spend = round(n_exposed_treat * COST_PER_EXPOSED_USER[channel], 2)
        attributed = float(revenue[(group == "treatment") & (exposed == 1)].sum())
        cat_rows.append((exp_id, name, f"ch_{channel}", start.date(), end.date(), 14, 0.05, spend, round(attributed, 2)))
        e_t = 1 - treat_miss
        truth[exp_id] = {
            "true_relative_lift_among_exposed": lift, "baseline_rate": p0,
            "expected_compliance_gap": e_t - ctrl_exposed,
            "expected_itt_relative_lift": lift * (e_t - ctrl_exposed) * 1.0 / (1 + lift * ctrl_exposed),
            "n_units": n,
        }
    catalog = pd.DataFrame(cat_rows, columns=["experiment_id", "experiment_name", "channel_id", "start_date",
                                              "end_date", "outcome_window_days", "planned_alpha",
                                              "test_spend_usd", "attributed_revenue_usd"])
    catalog.insert(2, "hypothesis", catalog.experiment_id.map(HYPOTHESES))
    assign = pd.concat(frames, ignore_index=True)
    return catalog, assign, truth
