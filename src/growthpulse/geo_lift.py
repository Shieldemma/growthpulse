"""Geo-lift (geo holdout) analysis by difference-in-differences.

Design: the campaign is OFF in every geo during a pre-period, then switched ON in a randomly chosen half of the geos
(treatment) while the other half stay OFF (control). The effect is the extra daily conversions in treatment geos relative
to what control geos' movement says would have happened anyway.

Estimators
  * DiD regression  y_gt = geo FE + date FE + tau * (treated_g x post_t) with standard errors clustered by geo.
  * Randomisation inference: re-assign treatment labels across geos many times; p-value = how often a placebo effect is
    as large as the real one. Robust when the number of geos is small.
  * Pre-period placebo: pretend the campaign started mid-way through the pre-period; the estimate should be ~0
    (a check of the parallel-trends assumption, not a proof of it).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


def _prepare(df: pd.DataFrame, test_start) -> pd.DataFrame:
    d = df.copy()
    d["activity_date"] = pd.to_datetime(d["activity_date"])
    d["treated"] = (d.assigned_group == "treatment").astype(int)
    d["post"] = (d.activity_date >= pd.Timestamp(test_start)).astype(int)
    return d


def did_estimate(d: pd.DataFrame, outcome: str = "conversions") -> dict:
    """Two-way fixed-effects DiD with geo-clustered SEs."""
    d = d.assign(did=d.treated * d.post, day=d.activity_date.dt.strftime("%Y-%m-%d"))
    m = smf.ols(f"{outcome} ~ did + C(geo_id) + C(day)", data=d).fit(cov_type="cluster", cov_kwds={"groups": d.geo_id})
    tau, se = float(m.params["did"]), float(m.bse["did"])
    lo, hi = (float(x) for x in m.conf_int().loc["did"])
    return {"tau": tau, "se": se, "ci_low": lo, "ci_high": hi, "p_value": float(m.pvalues["did"])}


def _did_fast(wide: np.ndarray, treated: np.ndarray, post_mask: np.ndarray) -> float:
    pre, post = wide[:, ~post_mask].mean(1), wide[:, post_mask].mean(1)
    delta = post - pre
    return float(delta[treated].mean() - delta[~treated].mean())


def randomisation_inference(d: pd.DataFrame, outcome: str = "conversions", n_perm: int = 5000, seed: int = 11) -> dict:
    wide = d.pivot(index="geo_id", columns="activity_date", values=outcome)
    geo_treated = d.groupby("geo_id").treated.first().reindex(wide.index).values.astype(bool)
    post_mask = np.asarray(wide.columns >= d[d.post == 1].activity_date.min())
    obs = _did_fast(wide.values, geo_treated, post_mask)
    rng = np.random.default_rng(seed)
    k = int(geo_treated.sum())
    null = np.empty(n_perm)
    for i in range(n_perm):
        t = np.zeros(len(geo_treated), bool)
        t[rng.choice(len(geo_treated), k, replace=False)] = True
        null[i] = _did_fast(wide.values, t, post_mask)
    return {"observed": obs, "p_value": float((np.abs(null) >= abs(obs) - 1e-12).mean()), "null_sd": float(null.std())}


def pre_period_placebo(d: pd.DataFrame, outcome: str = "conversions") -> dict:
    pre = d[d.post == 0].copy()
    mid = pre.activity_date.min() + (pre.activity_date.max() - pre.activity_date.min()) / 2
    pre["post"] = (pre.activity_date >= mid).astype(int)
    r = did_estimate(pre, outcome)
    return {"placebo_tau": r["tau"], "placebo_p_value": r["p_value"]}


def analyze_geo_lift(outcomes: pd.DataFrame, catalog_row: pd.Series, alpha: float = 0.05) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (one-row result table, weekly series for the chart)."""
    d = _prepare(outcomes, catalog_row.test_start_date)
    est = did_estimate(d)
    ri = randomisation_inference(d)
    pl = pre_period_placebo(d)
    t_post = d[(d.treated == 1) & (d.post == 1)]
    n_t_geos = d[d.treated == 1].geo_id.nunique()
    test_days = d[d.post == 1].activity_date.nunique()
    cf_mean_per_geo_day = t_post.conversions.mean() - est["tau"]          # counterfactual = observed - effect
    rel = est["tau"] / cf_mean_per_geo_day if cf_mean_per_geo_day > 0 else float("nan")
    rel_lo, rel_hi = est["ci_low"] / cf_mean_per_geo_day, est["ci_high"] / cf_mean_per_geo_day
    inc_conv = est["tau"] * n_t_geos * test_days
    avg_rev = d[d.conversions > 0].revenue_usd.sum() / max(d.conversions.sum(), 1)
    spend = float(d.spend_usd.sum())
    inc_rev = inc_conv * avg_rev
    mde = 2.8 * est["se"] / cf_mean_per_geo_day if cf_mean_per_geo_day > 0 else float("nan")
    sig = est["p_value"] < alpha and ri["p_value"] < alpha
    res = pd.DataFrame([{
        "experiment_id": catalog_row.experiment_id, "experiment_name": catalog_row.experiment_name,
        "hypothesis": catalog_row.hypothesis, "n_geos": int(d.geo_id.nunique()), "n_treatment_geos": int(n_t_geos),
        "pre_days": int(d[d.post == 0].activity_date.nunique()), "test_days": int(test_days),
        "tau_conversions_per_geo_day": est["tau"], "tau_ci_low": est["ci_low"], "tau_ci_high": est["ci_high"],
        "rel_lift": rel, "rel_lift_ci_low": rel_lo, "rel_lift_ci_high": rel_hi,
        "p_value_did_clustered": est["p_value"], "p_value_randomisation": ri["p_value"],
        "placebo_pre_period_tau": pl["placebo_tau"], "placebo_p_value": pl["placebo_p_value"],
        "parallel_trends_ok": bool(pl["placebo_p_value"] > 0.10), "mde_relative_approx": mde,
        "incremental_conversions": inc_conv, "incremental_revenue_usd": inc_rev, "test_spend_usd": spend,
        "incremental_roas": inc_rev / spend if spend > 0 else float("nan"),
        "incremental_cpa": spend / inc_conv if inc_conv > 0 else float("nan"), "significant": bool(sig),
        "verdict": ("Positive incremental effect (cluster-robust and randomisation tests agree)." if sig and est["tau"] > 0 else
                    "Inconclusive: effect not distinguishable from zero with this many geos.")}])
    d["week_start"] = (d.activity_date - pd.to_timedelta(d.activity_date.dt.dayofweek, unit="D")).dt.date
    w = d.groupby(["week_start", "assigned_group"]).agg(conversions=("conversions", "sum"), geo_days=("geo_id", "size")).reset_index()
    w["conversions_per_geo_day"] = w.conversions / w.geo_days
    base = w[w.week_start < pd.Timestamp(catalog_row.test_start_date).date()].groupby("assigned_group").conversions_per_geo_day.mean()
    w["indexed_to_pre_period"] = w.conversions_per_geo_day / w.assigned_group.map(base)
    w["is_test_period"] = (pd.to_datetime(w.week_start) >= pd.Timestamp(catalog_row.test_start_date)).astype(int)
    w.insert(0, "experiment_id", catalog_row.experiment_id)
    return res, w
