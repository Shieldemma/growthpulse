"""Every assumption of the SYNTHETIC world lives here, so it is transparent.

Nothing in this file describes a real company. Change a number, regenerate
the data (`python scripts/generate_data.py`), and re-run the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass

CHANNEL_NAMES = [
    # (name, group, is_paid)
    ("paid_search", "paid", 1),
    ("paid_social", "paid", 1),
    ("display", "paid", 1),
    ("affiliate", "paid", 1),
    ("organic_search", "organic", 0),
    ("email", "owned", 0),
    ("referral", "organic", 0),
    ("direct", "organic", 0),
]
PAID = ["paid_search", "paid_social", "display", "affiliate"]
FREE = ["organic_search", "email", "referral", "direct"]

# campaign_id: (channel, name, objective, share_of_channel_budget, cpc_multiplier,
#               quality_multiplier (signup propensity), start_week, end_week)
CAMPAIGNS = {
    "ps_brand": ("paid_search", "Search - Brand terms", "capture brand demand", 0.22, 0.45, 1.9, 0, None),
    "ps_generic": ("paid_search", "Search - Generic terms", "acquire new demand", 0.55, 1.00, 1.0, 0, None),
    "ps_competitor": ("paid_search", "Search - Competitor terms", "conquest", 0.23, 1.35, 0.75, 0, 100),
    "so_prospecting": ("paid_social", "Social - Prospecting", "awareness + leads", 0.45, 1.00, 1.0, 0, None),
    "so_lookalike": ("paid_social", "Social - Lookalike audiences", "efficient leads", 0.35, 1.10, 1.35, 0, None),
    "so_video": ("paid_social", "Social - Video", "awareness", 0.20, 0.80, 0.70, 30, None),
    "dp_prospecting": ("display", "Display - Prospecting", "awareness", 0.60, 1.00, 1.0, 0, None),
    "dp_programmatic": ("display", "Display - Programmatic", "reach", 0.40, 0.80, 0.70, 0, None),
    "af_coupon": ("affiliate", "Affiliate - Coupon sites", "discount seekers", 0.60, 1.00, 1.0, 0, None),
    "af_content": ("affiliate", "Affiliate - Content partners", "review-driven leads", 0.40, 1.20, 1.4, 0, None),
}

PLANS = [("plan_starter", "Starter", 49.0), ("plan_growth", "Growth", 129.0), ("plan_scale", "Scale", 349.0)]

# Plan mix by FIRST-TOUCH channel: (starter, growth, scale)
PLAN_MIX = {
    "paid_search": (0.42, 0.42, 0.16),
    "paid_social": (0.58, 0.34, 0.08),
    "display": (0.66, 0.29, 0.05),
    "affiliate": (0.70, 0.27, 0.03),
    "organic_search": (0.42, 0.42, 0.16),
    "email": (0.45, 0.42, 0.13),
    "referral": (0.38, 0.43, 0.19),
    "direct": (0.38, 0.42, 0.20),
}

MONTH_DEMAND = [1.08, 1.04, 1.06, 1.02, 1.00, 0.97, 0.90, 0.88, 1.07, 1.08, 1.00, 0.82]

# Promotions: (name, (month, day) start, (month, day) end) -> repeated every year
PROMOS = [
    ("Spring Sale", (3, 10), (3, 24)),
    ("Back To Work", (9, 8), (9, 22)),
    ("Black Friday", (11, 24), (12, 1)),
]


@dataclass(frozen=True)
class GenConfig:
    seed: int = 42
    scale: float = 1.0                 # multiplies traffic volume; 0.15 is used in tests
    start_date: str = "2023-01-02"     # a Monday
    end_date: str = "2025-12-28"       # a Sunday  -> exactly 156 weeks
    gross_margin: float = 0.80         # documented assumption used for gross-profit LTV

    # --- paid media ---------------------------------------------------
    base_daily_spend: tuple = (("paid_search", 520.0), ("paid_social", 400.0),
                               ("display", 210.0), ("affiliate", 150.0))
    spend_growth_per_year: float = 0.12
    flight_sigma: float = 0.30         # AR(1) innovation sd of log weekly budget (creates variation for the MMM)
    flight_phi: float = 0.45
    burst_prob: float = 0.07           # share of weeks with a 1.8x burst
    pause_prob: float = 0.06           # share of weeks with a 0.35x pullback
    base_cpc: tuple = (("paid_search", 9.0), ("paid_social", 6.0), ("display", 2.6), ("affiliate", 5.0))
    cpc_inflation_per_year: float = 0.05
    # Diminishing returns: clicks ~ spend^(1-gamma) at campaign-day level
    cpc_spend_elasticity: tuple = (("paid_search", 0.32), ("paid_social", 0.22),
                                   ("display", 0.12), ("affiliate", 0.10))
    ctr: tuple = (("paid_search", 0.045), ("paid_social", 0.011), ("display", 0.004), ("affiliate", 0.020))
    click_to_session_rate: float = 0.95

    # --- non-paid traffic (new visitors per day at scale=1) -----------
    free_daily_visitors: tuple = (("organic_search", 85.0), ("email", 7.0),
                                  ("referral", 17.0), ("direct", 33.0))
    free_growth_per_year: float = 0.22
    halo_strength: float = 0.25        # lift of organic/direct traffic from paid social+display awareness (carryover)
    halo_decay_per_day: float = 0.93
    brand_displacement: float = 0.55   # share of brand-search clicks that would have arrived via organic search anyway

    # --- journeys & conversion ---------------------------------------
    extra_session_lambda: tuple = (("paid_search", 0.65), ("paid_social", 0.40), ("display", 0.26),
                                   ("affiliate", 0.45), ("organic_search", 0.60), ("direct", 0.80),
                                   ("email", 1.0), ("referral", 0.45))
    return_channel_mix: tuple = (("direct", 0.36), ("organic_search", 0.28), ("email", 0.24), ("referral", 0.12))
    max_journey_days: int = 30
    signup_base: tuple = (("paid_search", 0.050), ("paid_social", 0.030), ("display", 0.016),
                          ("affiliate", 0.042), ("organic_search", 0.052), ("direct", 0.085),
                          ("email", 0.120), ("referral", 0.062))
    promo_signup_multiplier: float = 1.28
    trial_start_rate: float = 0.92
    trial_to_paid: tuple = (("paid_search", 0.36), ("paid_social", 0.30), ("display", 0.22),
                            ("affiliate", 0.30), ("organic_search", 0.36), ("direct", 0.44),
                            ("email", 0.48), ("referral", 0.42))
    trial_days: int = 14

    # --- churn / revenue ----------------------------------------------
    monthly_churn_floor: tuple = (("plan_starter", 0.045), ("plan_growth", 0.028), ("plan_scale", 0.016))
    churn_channel_mult: tuple = (("paid_search", 0.9), ("paid_social", 1.1), ("display", 1.35),
                                 ("affiliate", 1.5), ("organic_search", 0.8), ("direct", 0.7),
                                 ("email", 0.7), ("referral", 0.65))
    early_churn_boost: float = 2.0     # hazard x (1 + boost*exp(-(k-1)/tau))
    early_churn_tau: float = 3.0
    refund_prob_first_payment: float = 0.05
    refund_prob_renewal: float = 0.012

    # --- experiments (ground truth is stored OUTSIDE the warehouse) -----
    experiments: tuple = (
        # id, name, channel, n_units, baseline_p, true_relative_lift, control_exposed, treat_not_exposed
        ("EXP-001", "Paid social lookalike holdout", "paid_social", 60000, 0.020, 0.25, 0.010, 0.06),
        ("EXP-002", "Display prospecting holdout", "display", 80000, 0.016, 0.00, 0.010, 0.07),
        ("EXP-003", "Affiliate coupon pilot (small)", "affiliate", 6000, 0.030, 0.10, 0.000, 0.05),
    )

    def d(self, name: str) -> dict:
        return dict(getattr(self, name))
