"""Build the static, recruiter-facing web dashboard (docs/index.html).

Reads only the BI exports in dashboard/bi_exports/ (written by scripts/run_pipeline.py),
aggregates them into one small JSON payload and injects it into dashboard/web/template.html.
The output is a single self-contained HTML file that GitHub Pages can serve from /docs.

    python scripts/build_web_dashboard.py            # -> docs/index.html
    python scripts/build_web_dashboard.py --fragment # also writes dashboard/web/dashboard_fragment.html

Every number on the page is computed here from the exports, so the page and the
business report cannot drift apart.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "dashboard" / "bi_exports"
TEMPLATE = ROOT / "dashboard" / "web" / "template.html"
OUT = ROOT / "docs" / "index.html"
FRAGMENT = ROOT / "dashboard" / "web" / "dashboard_fragment.html"

PAID = ["paid_search", "paid_social", "display", "affiliate"]
ORGANIC = ["organic_search", "direct", "referral", "email"]
LABEL = {
    "paid_search": "Paid search", "paid_social": "Paid social", "display": "Display",
    "affiliate": "Affiliate", "organic_search": "Organic search", "direct": "Direct",
    "referral": "Referral", "email": "Email",
}


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(EXPORTS / f"{name}.csv")


def clean(obj):
    """Round floats and turn NaN/inf into None so the JSON is small and valid."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return round(obj, 4)
    if hasattr(obj, "item"):  # numpy scalar
        return clean(obj.item())
    return obj


def ratio(a: float, b: float):
    return a / b if b else None


def build_payload() -> dict:
    econ = read("bi_channel_economics").set_index("channel_name")
    fresh = read("bi_data_freshness").iloc[0]

    # ---- headline KPIs (paid media, first-touch) -------------------------------------
    paid = econ.loc[PAID]
    paid_spend = float(paid.spend_usd.sum())
    paid_customers = float(paid.new_customers.sum())
    total_customers = float(econ.new_customers.sum())
    ue = read("rpt_unit_economics_monthly")
    ue_paid = ue[ue.channel_name.isin(PAID)]
    roas_m12 = ratio(ue_paid.revenue_m12_eligible.sum(), ue_paid.spend_eligible_m12.sum())
    kpis = {
        "paid_spend": paid_spend,
        "paid_customers": paid_customers,
        "total_customers": total_customers,
        "paid_cac": ratio(paid_spend, paid_customers),
        "paid_roas_m12": roas_m12,
        "paid_share_of_spend_search": float(econ.loc["paid_search", "spend_usd"]) / paid_spend,
        "paid_share_of_customers_search": float(econ.loc["paid_search", "new_customers"]) / paid_customers,
        "loss_making_spend_share": float(econ.loc[["display", "paid_social"], "spend_usd"].sum()) / paid_spend,
    }

    channels = []
    for ch in PAID + ORGANIC:
        r = econ.loc[ch]
        channels.append({
            "id": ch, "label": LABEL[ch], "paid": ch in PAID,
            "spend": r.spend_usd, "customers": r.new_customers, "signups": r.signups,
            "cpc": r.cpc, "cac": r.cac_paid_media, "cac_loaded": r.cac_fully_loaded,
            "rev_per_customer_12m": r.revenue_per_customer_window, "roas_12m": r.roas_window,
            "monthly_churn": r.monthly_churn_hazard_m3_12, "ltv_gp_36m": r.projected_gp_ltv_36m,
            "ltv_cac": r.ltv_cac_projected_loaded, "payback_months": r.payback_months_loaded,
        })

    # ---- monthly trend --------------------------------------------------------------
    ue["month"] = ue.year_month
    months = sorted(ue.month.unique())
    spend_by_ch = {ch: [float(ue[(ue.month == m) & (ue.channel_name == ch)].spend_usd.sum()) for m in months] for ch in PAID}
    cust_paid = [float(ue[(ue.month == m) & ue.channel_name.isin(PAID)].new_customers.sum()) for m in months]
    cust_org = [float(ue[(ue.month == m) & ue.channel_name.isin(ORGANIC)].new_customers.sum()) for m in months]
    cac_by_month = [ratio(sum(spend_by_ch[c][i] for c in PAID), cust_paid[i]) for i in range(len(months))]

    # ---- funnel ---------------------------------------------------------------------
    fun = read("rpt_funnel_daily")
    stages = ["visitors", "pricing_viewers", "signup_starters", "signups", "trials", "paying_customers"]
    funnel_all = [float(fun[s].sum()) for s in stages]
    fun["group"] = fun.channel_name.where(fun.channel_name.isin(PAID), "organic_owned")
    funnel_by = {}
    for g, d in fun.groupby("group"):
        funnel_by[g] = [float(d[s].sum()) for s in stages]
    device = {}
    for g, d in fun.groupby("device_category"):
        device[g] = {"visitors": float(d.visitors.sum()), "paying": float(d.paying_customers.sum())}

    # ---- retention curves (customer-weighted, months 0..24) ---------------------------
    ret = read("rpt_retention_cohort")
    ret["group"] = ret.channel_name.where(ret.channel_name.isin(PAID), "organic_owned")
    retention = {}
    for g, d in ret.groupby("group"):
        agg = d.groupby("months_since_start")[["customers_retained", "customers_observed"]].sum()
        agg = agg[agg.index <= 24]
        retention[g] = [ratio(a, b) for a, b in zip(agg.customers_retained, agg.customers_observed)]

    # ---- attribution: customers credited by model -------------------------------------
    att = read("rpt_attribution_monthly")
    attribution = {}
    for model, d in att.groupby("attribution_model"):
        attribution[model] = {ch: float(d[d.channel_name == ch].new_customers.sum()) for ch in PAID}

    # ---- experiments -----------------------------------------------------------------
    exp = read("bi_experiment_results")
    experiments = [{
        "id": r.experiment_id, "name": r.experiment_name, "channel": r.channel_id.replace("ch_", ""),
        "rel_lift": r.rel_lift, "lo": r.rel_lift_ci_low, "hi": r.rel_lift_ci_high, "p": r.p_value,
        "significant": bool(r.significant), "attributed_roas": r.attributed_roas,
        "incremental_roas": r.incremental_roas, "n": int(r.n_treatment + r.n_control),
        "required_n": int(r.required_n_per_arm_for_observed_lift), "verdict": r.verdict,
        "type": "User-level holdout",
    } for r in exp.itertuples()]
    geo = read("bi_geo_lift_results").iloc[0]
    experiments.append({
        "id": geo.experiment_id, "name": geo.experiment_name, "channel": "paid_search",
        "rel_lift": geo.rel_lift, "lo": geo.rel_lift_ci_low, "hi": geo.rel_lift_ci_high,
        "p": geo.p_value_randomisation, "significant": bool(geo.significant), "attributed_roas": None,
        "incremental_roas": geo.incremental_roas, "n": int(geo.n_geos), "required_n": None,
        "verdict": geo.verdict, "type": "Geo holdout (diff-in-diff)",
        "placebo_p": geo.placebo_p_value, "parallel_ok": bool(geo.parallel_trends_ok),
    })
    gw = read("bi_geo_lift_weekly")
    geo_weekly = {
        "weeks": sorted(gw.week_start.unique().tolist()),
        "control": gw[gw.assigned_group == "control"].sort_values("week_start").indexed_to_pre_period.tolist(),
        "treatment": gw[gw.assigned_group == "treatment"].sort_values("week_start").indexed_to_pre_period.tolist(),
        "test_start": gw[gw.is_test_period == 1].week_start.min(),
    }
    life = read("bi_lifecycle_results")
    lifecycle = [{"metric": r.metric, "horizon": int(r.horizon_days), "rel": r.rel_lift, "lo": r.rel_ci_low,
                  "hi": r.rel_ci_high, "p": r.p_value, "control": r.control, "treatment": r.treatment,
                  "kind": r.kind} for r in life.itertuples()]
    lv = read("bi_lifecycle_value")
    lifecycle_value = [{"horizon": int(r.horizon_days), "net_per_user": r.net_value_per_treated_user,
                        "lo": r.net_value_ci_low, "hi": r.net_value_ci_high, "total": r.total_net_value_usd,
                        "roi": r.roi_on_program_cost} for r in lv.itertuples()]

    # ---- MMM ------------------------------------------------------------------------
    mmm_ch = read("bi_mmm_channel_summary")
    mmm_channels = [{"id": r.channel, "roi": r.avg_roi, "lo": r.avg_roi_p05, "hi": r.avg_roi_p95,
                     "share": r.share_of_revenue, "share_lo": r.share_p05, "share_hi": r.share_p95,
                     "decay": r.decay, "lag": int(r.lag_weeks), "marginal": r.marginal_weekly_mrr_per_extra_usd,
                     "weekly_spend": r.current_weekly_spend_usd} for r in mmm_ch.itertuples()]
    cal = read("bi_mmm_calibration")
    calibration = [{"id": r.channel, "exp": r.experiment_id, "exp_roas": r.experiment_incremental_roas,
                    "mmm": r.mmm_avg_roi, "lo": r.mmm_roi_p05, "hi": r.mmm_roi_p95,
                    "inside": bool(r.experiment_inside_mmm_interval), "exp_sig": bool(r.experiment_significant),
                    "reading": r.reading} for r in cal.itertuples()]
    comp = read("bi_mmm_model_comparison")
    model_comp = [{"model": r.model, "r2": r.test_r2, "mape": r.test_mape, "rmse": r.test_rmse,
                   "chosen": bool(r.chosen_for_decisions)} for r in comp.itertuples()]
    diag = read("bi_mmm_diagnostics")
    diagnostics = diag.to_dict(orient="records")
    sc = read("bi_mmm_scenarios")
    scenarios = [{"name": r.scenario, "budget": r.weekly_budget_usd, "mrr": r.predicted_weekly_media_mrr,
                  "delta": r.delta_vs_current, "lo": r.delta_p05, "hi": r.delta_p95,
                  "prob": r.prob_better_than_current,
                  "spend": {c: getattr(r, f"spend_{c}") for c in PAID}} for r in sc.itertuples()]
    curves = read("bi_mmm_response_curves")
    response = {c: {"x": d.weekly_spend_usd.tolist(), "y": d.weekly_mrr.tolist()} for c, d in curves.groupby("channel")}
    fit = read("bi_mmm_fit")
    mmm_fit = {"weeks": fit.week_start.tolist(), "actual": fit.new_mrr_usd.tolist(),
               "fitted": fit.fitted.tolist(), "test_start": fit[fit.is_test_period == 1].week_start.min()}

    # ---- recommendations -------------------------------------------------------------
    rec = read("bi_recommendations")
    recommendations = [{"id": r.channel, "action": r.recommended_action, "rule": r.rule_triggered,
                        "evidence": r.evidence, "caveats": r.caveats} for r in rec.itertuples()]

    return clean({
        "meta": {"data_start": fresh.data_start_date, "data_end": fresh.data_end_date,
                 "built": str(fresh.pipeline_finished_utc)[:16], "dbt_models": int(fresh.dbt_models_built),
                 "dbt_tests_passed": int(fresh.dbt_tests_passed), "dbt_tests_failed": int(fresh.dbt_tests_failed),
                 "seed": int(fresh.generator_seed), "synthetic": bool(fresh.is_synthetic)},
        "labels": LABEL, "paid": PAID, "kpis": kpis, "channels": channels,
        "monthly": {"months": months, "spend": spend_by_ch, "cust_paid": cust_paid, "cust_org": cust_org,
                    "cac": cac_by_month},
        "funnel": {"stages": stages, "all": funnel_all, "by": funnel_by, "device": device},
        "retention": retention, "attribution": attribution,
        "experiments": experiments, "geo_weekly": geo_weekly,
        "lifecycle": lifecycle, "lifecycle_value": lifecycle_value,
        "mmm": {"channels": mmm_channels, "calibration": calibration, "models": model_comp,
                "diagnostics": diagnostics, "scenarios": scenarios, "response": response, "fit": mmm_fit},
        "recommendations": recommendations,
    })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fragment", action="store_true", help="also write the body-only fragment")
    args = ap.parse_args()

    payload = json.dumps(build_payload(), separators=(",", ":"))
    body = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    head, rest = body.split('<header class="topbar">', 1)  # title/meta/styles go in <head>
    OUT.write_text(
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
        + head + "</head>\n<body>\n<header class=\"topbar\">" + rest + "\n</body>\n</html>\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024:.0f} KB)")
    if args.fragment:
        FRAGMENT.write_text(body, encoding="utf-8")
        print(f"wrote {FRAGMENT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
