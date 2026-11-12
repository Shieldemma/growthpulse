"""Incrementality analysis for treatment/control (holdout) experiments.

Primary estimand = INTENT-TO-TREAT (ITT): compare everyone ASSIGNED to treatment with everyone assigned to control.
ITT is protected by randomisation even when some treated users never saw the ads (non-compliance) and some control
users did (contamination). A second estimate (CACE / Wald) rescales ITT by the exposure gap to approximate the effect
ON THE EXPOSED; it needs the extra assumption that assignment affects conversion only through exposure.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------- basic estimators
def two_proportion_ztest(x_t: int, n_t: int, x_c: int, n_c: int) -> tuple[float, float]:
    """Pooled two-sided z-test of H0: p_t == p_c. Returns (z, p_value)."""
    if min(n_t, n_c) == 0:
        return float("nan"), float("nan")
    p_pool = (x_t + x_c) / (n_t + n_c)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n_t + 1 / n_c))
    if se == 0:
        return float("nan"), float("nan")
    z = (x_t / n_t - x_c / n_c) / se
    return z, 2 * (1 - stats.norm.cdf(abs(z)))


def newcombe_diff_ci(x_t, n_t, x_c, n_c, conf=0.95) -> tuple[float, float]:
    """Newcombe (hybrid Wilson score) CI for p_t - p_c; behaves well for small rates / samples."""
    z = stats.norm.ppf(1 - (1 - conf) / 2)

    def wilson(x, n):
        p = x / n
        den = 1 + z * z / n
        centre = (p + z * z / (2 * n)) / den
        half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
        return centre - half, centre + half

    l1, u1 = wilson(x_t, n_t)
    l2, u2 = wilson(x_c, n_c)
    d = x_t / n_t - x_c / n_c
    lo = d - math.sqrt((x_t / n_t - l1) ** 2 + (u2 - x_c / n_c) ** 2)
    hi = d + math.sqrt((u1 - x_t / n_t) ** 2 + (x_c / n_c - l2) ** 2)
    return lo, hi


def relative_lift_ci(x_t, n_t, x_c, n_c, conf=0.95) -> tuple[float, float, float]:
    """Relative lift (p_t/p_c - 1) with a Katz log-ratio CI. NaN if either arm has zero conversions."""
    if x_t == 0 or x_c == 0:
        return float("nan"), float("nan"), float("nan")
    z = stats.norm.ppf(1 - (1 - conf) / 2)
    rr = (x_t / n_t) / (x_c / n_c)
    se = math.sqrt(1 / x_t - 1 / n_t + 1 / x_c - 1 / n_c)
    return rr - 1, math.exp(math.log(rr) - z * se) - 1, math.exp(math.log(rr) + z * se) - 1


# ---------------------------------------------------------------- power
def required_sample_size_per_arm(p_baseline: float, relative_mde: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """Per-arm n to detect a relative lift `relative_mde` with a two-sided two-proportion test."""
    p1, p2 = p_baseline, p_baseline * (1 + relative_mde)
    za, zb = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    pbar = (p1 + p2) / 2
    num = (za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return int(math.ceil(num / (p2 - p1) ** 2))


def minimum_detectable_effect(p_baseline: float, n_per_arm: int, alpha: float = 0.05, power: float = 0.8) -> float:
    """Smallest RELATIVE lift detectable with `n_per_arm` per arm (bisection on required_sample_size)."""
    lo, hi = 1e-4, 5.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if required_sample_size_per_arm(p_baseline, mid, alpha, power) > n_per_arm:
            lo = mid
        else:
            hi = mid
    return hi


def achieved_power(p_baseline: float, relative_lift: float, n_per_arm: int, alpha: float = 0.05) -> float:
    p1, p2 = p_baseline, p_baseline * (1 + relative_lift)
    se = math.sqrt(p1 * (1 - p1) / n_per_arm + p2 * (1 - p2) / n_per_arm)
    za = stats.norm.ppf(1 - alpha / 2)
    return float(1 - stats.norm.cdf(za - abs(p2 - p1) / se) + stats.norm.cdf(-za - abs(p2 - p1) / se))


# ---------------------------------------------------------------- design checks
def srm_check(n_t: int, n_c: int, expected_treat_share: float = 0.5) -> dict:
    """Sample-ratio-mismatch chi-square test. Small p (< 0.001) = broken randomisation/logging."""
    n = n_t + n_c
    chi2 = (n_t - n * expected_treat_share) ** 2 / (n * expected_treat_share) + \
           (n_c - n * (1 - expected_treat_share)) ** 2 / (n * (1 - expected_treat_share))
    return {"chi2": chi2, "p_value": float(1 - stats.chi2.cdf(chi2, 1)), "ok": (1 - stats.chi2.cdf(chi2, 1)) >= 0.001}


def covariate_balance(df: pd.DataFrame) -> pd.DataFrame:
    """Balance of pre-treatment covariates: standardised mean difference (|SMD| < 0.1 is the usual rule of thumb)
    and a chi-square / t-test p-value (one test per covariate - expect ~5% to fall below 0.05 by chance)."""
    rows = []
    t, c = df[df.assigned_group == "treatment"], df[df.assigned_group == "control"]
    # numeric
    m1, m0 = t.prior_sessions.mean(), c.prior_sessions.mean()
    sd = math.sqrt((t.prior_sessions.var() + c.prior_sessions.var()) / 2)
    rows.append({"covariate": "prior_sessions", "smd": (m1 - m0) / sd if sd else 0.0,
                 "p_value": float(stats.ttest_ind(t.prior_sessions, c.prior_sessions, equal_var=False).pvalue)})
    for dev in sorted(df.device_category.unique()):
        p1, p0 = (t.device_category == dev).mean(), (c.device_category == dev).mean()
        pp = (p1 + p0) / 2
        sdv = math.sqrt(pp * (1 - pp)) if 0 < pp < 1 else 1.0
        tab = pd.crosstab(df.assigned_group, df.device_category == dev)
        pval = float(stats.chi2_contingency(tab)[1]) if tab.shape == (2, 2) else float("nan")
        rows.append({"covariate": f"device={dev}", "smd": (p1 - p0) / sdv, "p_value": pval})
    out = pd.DataFrame(rows)
    out["balanced"] = out.smd.abs() < 0.1
    return out


# ---------------------------------------------------------------- full analysis
@dataclass
class ExperimentResult:
    experiment_id: str
    n_treatment: int
    n_control: int
    conv_treatment: int
    conv_control: int
    rate_treatment: float
    rate_control: float
    abs_lift: float
    abs_lift_ci_low: float
    abs_lift_ci_high: float
    rel_lift: float
    rel_lift_ci_low: float
    rel_lift_ci_high: float
    z: float
    p_value: float
    significant: bool
    srm_p_value: float
    srm_ok: bool
    exposure_rate_treatment: float
    exposure_rate_control: float
    cace_abs_lift: float          # effect on the exposed (Wald/IV estimate)
    cace_rel_lift: float
    mde_relative: float           # minimum detectable relative lift at 80% power with this sample
    power_at_observed_lift: float
    required_n_per_arm_for_observed_lift: float
    incremental_conversions: float   # ITT abs lift x treated units
    incremental_revenue_usd: float
    test_spend_usd: float
    incremental_roas: float
    attributed_roas: float
    incremental_cpa: float
    attributed_cpa: float
    verdict: str

    def to_dict(self):
        return asdict(self)


def analyze_experiment(df: pd.DataFrame, spend_usd: float, attributed_revenue_usd: float, experiment_id: str = "",
                       alpha: float = 0.05, margin: float | None = None) -> ExperimentResult:
    t, c = df[df.assigned_group == "treatment"], df[df.assigned_group == "control"]
    n_t, n_c = len(t), len(c)
    x_t, x_c = int(t.converted.sum()), int(c.converted.sum())
    p_t, p_c = x_t / n_t, x_c / n_c
    z, pval = two_proportion_ztest(x_t, n_t, x_c, n_c)
    lo, hi = newcombe_diff_ci(x_t, n_t, x_c, n_c, 1 - alpha)
    rel, rlo, rhi = relative_lift_ci(x_t, n_t, x_c, n_c, 1 - alpha)
    srm = srm_check(n_t, n_c)
    e_t, e_c = t.was_exposed.mean(), c.was_exposed.mean()
    gap = e_t - e_c
    cace = (p_t - p_c) / gap if gap > 0 else float("nan")
    p_c_unexposed = p_c  # baseline approximation for relative CACE
    cace_rel = cace / p_c_unexposed if p_c_unexposed > 0 else float("nan")
    mde = minimum_detectable_effect(p_c, min(n_t, n_c)) if p_c > 0 else float("nan")
    pow_obs = achieved_power(p_c, rel if not math.isnan(rel) else 0.0, min(n_t, n_c)) if p_c > 0 else float("nan")
    req = required_sample_size_per_arm(p_c, abs(rel)) if (p_c > 0 and not math.isnan(rel) and abs(rel) > 1e-6) else float("nan")
    avg_rev = df.loc[df.converted == 1, "revenue_usd"].mean() if df.converted.sum() else 0.0
    inc_conv = (p_t - p_c) * n_t
    inc_rev = inc_conv * avg_rev
    inc_roas = inc_rev / spend_usd if spend_usd > 0 else float("nan")
    att_roas = attributed_revenue_usd / spend_usd if spend_usd > 0 else float("nan")
    inc_cpa = spend_usd / inc_conv if inc_conv > 0 else float("nan")
    att_conv = int(t[(t.was_exposed == 1)].converted.sum())
    att_cpa = spend_usd / att_conv if att_conv > 0 else float("nan")
    significant = bool(pval < alpha) if not math.isnan(pval) else False
    if not srm["ok"]:
        verdict = "INVALID: sample-ratio mismatch - do not interpret until randomisation/logging is fixed."
    elif significant and lo > 0:
        verdict = "Positive incremental effect detected (CI excludes zero)."
    elif significant and hi < 0:
        verdict = "Negative effect detected (CI excludes zero)."
    else:
        verdict = ("Inconclusive: no significant effect. The data cannot distinguish zero from effects up to "
                   f"about +{hi / p_c:.0%} relative.") if p_c > 0 else "Inconclusive."
    return ExperimentResult(
        experiment_id, n_t, n_c, x_t, x_c, p_t, p_c, p_t - p_c, lo, hi, rel, rlo, rhi, z, pval, significant,
        srm["p_value"], srm["ok"], float(e_t), float(e_c), cace, cace_rel, mde, pow_obs, req, inc_conv, inc_rev,
        spend_usd, inc_roas, att_roas, inc_cpa, att_cpa, verdict)


def contamination_summary(df: pd.DataFrame) -> dict:
    t, c = df[df.assigned_group == "treatment"], df[df.assigned_group == "control"]
    return {"treatment_not_exposed_share": float(1 - t.was_exposed.mean()),
            "control_exposed_share": float(c.was_exposed.mean()),
            "interpretation": "Non-compliance dilutes ITT toward zero; control exposure (contamination) does too. "
                              "Both make ITT conservative, and they are why CACE is reported alongside it."}
