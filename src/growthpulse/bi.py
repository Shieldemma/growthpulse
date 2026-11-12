"""BI delivery layer: ONE registry of every table a BI tool (Looker Studio, Power BI, Tableau, Excel...) should read.

Two producers feed it:
  * dbt  (`reporting` models)  -> DuckDB schema gp_reporting  /  BigQuery dataset  <GP_BQ_DATASET>_reporting
  * Python (experiments, geo-lift, lifecycle, MMM, recommendations; written here as `bi_*`) -> DuckDB gp_bi / BigQuery <GP_BQ_DATASET>_analytics

From the registry we build: the Python-side BI tables, CSV exports for the local fallback, the BigQuery publisher, the
Looker Studio data-source URLs, and the field-definition documentation - so names can never drift between them.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import paths

BI_SCHEMA = "gp_bi"
REPORTING_SCHEMA = "gp_reporting"

# name, layer ('reporting' = dbt, 'analytics' = python), grain, purpose / report pages, date field for Looker date-range control
REGISTRY: list[dict] = [
    # ---- dbt reporting layer
    dict(name="rpt_dim_date", layer="reporting", grain="calendar day", pages="All (date dimension)", date_field="date_day"),
    dict(name="rpt_dim_channel", layer="reporting", grain="channel", pages="All (channel dimension / filter)", date_field=None),
    dict(name="rpt_dim_campaign", layer="reporting", grain="campaign", pages="Channel & campaign (campaign dimension / filter)", date_field=None),
    dict(name="rpt_marketing_daily", layer="reporting", grain="date x channel x campaign (first touch)",
         pages="1 Executive, 2 Channel & campaign, 4 CAC/LTV/ROAS", date_field="metric_date"),
    dict(name="rpt_unit_economics_monthly", layer="reporting", grain="acquisition month x channel (first touch)",
         pages="1 Executive, 4 CAC/LTV/ROAS", date_field="acquisition_month"),
    dict(name="rpt_funnel_daily", layer="reporting", grain="first-visit date x channel x campaign x device", pages="3 Funnel", date_field="first_session_date"),
    dict(name="rpt_retention_cohort", layer="reporting", grain="cohort month x channel x months since start", pages="3 Funnel & retention", date_field="cohort_month"),
    dict(name="rpt_attribution_monthly", layer="reporting", grain="month x attribution model x channel", pages="5 Attribution", date_field="month_start"),
    dict(name="rpt_mmm_weekly", layer="reporting", grain="week", pages="7 MMM (inputs / EDA)", date_field="week_start"),
    dict(name="rpt_customers", layer="reporting", grain="customer", pages="Drill-through", date_field="signup_date"),
    # ---- python analytics layer
    dict(name="bi_experiment_results", layer="analytics", grain="user-level experiment", pages="6 Experiments", date_field=None),
    dict(name="bi_geo_lift_results", layer="analytics", grain="geo experiment", pages="6 Experiments", date_field=None),
    dict(name="bi_geo_lift_weekly", layer="analytics", grain="week x group (geo experiment)", pages="6 Experiments", date_field="week_start"),
    dict(name="bi_lifecycle_results", layer="analytics", grain="lifecycle experiment x metric x horizon", pages="6 Experiments", date_field=None),
    dict(name="bi_lifecycle_value", layer="analytics", grain="lifecycle experiment x horizon", pages="6 Experiments", date_field=None),
    dict(name="bi_mmm_fit", layer="analytics", grain="week", pages="7 MMM", date_field="week_start"),
    dict(name="bi_mmm_contributions", layer="analytics", grain="week x component", pages="7 MMM", date_field="week_start"),
    dict(name="bi_mmm_channel_summary", layer="analytics", grain="channel", pages="7 MMM", date_field=None),
    dict(name="bi_mmm_response_curves", layer="analytics", grain="channel x weekly spend point", pages="7 MMM", date_field=None),
    dict(name="bi_mmm_scenarios", layer="analytics", grain="budget scenario", pages="7 MMM", date_field=None),
    dict(name="bi_mmm_scenario_spend", layer="analytics", grain="budget scenario x channel", pages="7 MMM", date_field=None),
    dict(name="bi_mmm_model_comparison", layer="analytics", grain="model", pages="7 MMM", date_field=None),
    dict(name="bi_mmm_diagnostics", layer="analytics", grain="diagnostic check", pages="7 MMM", date_field=None),
    dict(name="bi_mmm_calibration", layer="analytics", grain="channel x experiment", pages="7 MMM / 6 Experiments", date_field=None),
    dict(name="bi_recommendations", layer="analytics", grain="paid channel", pages="1 Executive", date_field=None),
    dict(name="bi_channel_economics", layer="analytics", grain="channel", pages="4 CAC/LTV/ROAS", date_field=None),
    dict(name="bi_data_freshness", layer="analytics", grain="pipeline run (1 row)", pages="8 Data quality & freshness", date_field="pipeline_finished_utc"),
]
BY_NAME = {r["name"]: r for r in REGISTRY}


def local_ref(name: str) -> str:
    return f"{REPORTING_SCHEMA if BY_NAME[name]['layer'] == 'reporting' else BI_SCHEMA}.{name}"


# ----------------------------------------------------------------------------- Python-side BI tables
def build_bi_tables(con, status_dir: Path | None = None, raw_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    A = paths.ANALYTICS
    q = lambda t: con.sql(f"select * from {A}.{t}").df()
    out: dict[str, pd.DataFrame] = {}
    e = q("experiment_results")
    e["experiment_type"] = "user-level holdout"
    out["bi_experiment_results"] = e
    out["bi_geo_lift_results"] = q("geo_lift_results")
    w = q("geo_lift_weekly")
    w["week_start"] = pd.to_datetime(w["week_start"])
    out["bi_geo_lift_weekly"] = w
    out["bi_lifecycle_results"] = q("lifecycle_results")
    out["bi_lifecycle_value"] = q("lifecycle_value")
    fit = q("mmm_fit")
    fit["week_start"] = pd.to_datetime(fit["week_start"])
    out["bi_mmm_fit"] = fit
    cw = q("mmm_contrib_weekly")
    cw["week_start"] = pd.to_datetime(cw["week_start"])
    long = cw.melt(id_vars="week_start", var_name="component", value_name="contribution_usd")
    long["component"] = long.component.str.replace("spend_", "", regex=False)
    long["is_media"] = (long.component != "baseline").astype(int)
    out["bi_mmm_contributions"] = long
    out["bi_mmm_channel_summary"] = q("mmm_channel_summary")
    out["bi_mmm_response_curves"] = q("mmm_response_curves")
    sc = q("mmm_budget_scenarios")
    out["bi_mmm_scenarios"] = sc
    spend_cols = [c for c in sc.columns if c.startswith("spend_")]
    sl = sc.melt(id_vars=["scenario", "weekly_budget_usd"], value_vars=spend_cols, var_name="channel", value_name="weekly_spend_usd")
    sl["channel"] = sl.channel.str.replace("spend_", "", regex=False)
    sl["share_of_budget"] = sl.weekly_spend_usd / sl.weekly_budget_usd
    cur = sl[sl.scenario.str.startswith("current")].set_index("channel").weekly_spend_usd
    sl["change_vs_current_usd"] = sl.weekly_spend_usd - sl.channel.map(cur)
    out["bi_mmm_scenario_spend"] = sl
    out["bi_mmm_model_comparison"] = q("mmm_model_comparison")
    out["bi_mmm_diagnostics"] = q("mmm_diagnostics")
    out["bi_mmm_calibration"] = q("mmm_calibration")
    out["bi_recommendations"] = q("recommendations")
    out["bi_channel_economics"] = q("channel_economics")
    # freshness / provenance
    status_dir = Path(status_dir or paths.DATA_PROCESSED)
    raw_dir = Path(raw_dir or paths.DATA_RAW)
    meta = json.loads((raw_dir / "_generation_metadata.json").read_text()) if (raw_dir / "_generation_metadata.json").exists() else {}
    res = json.loads((status_dir / "dbt_run_results.json").read_text()) if (status_dir / "dbt_run_results.json").exists() else []
    tests = [r for r in res if r["unique_id"].startswith("test.")]
    models = [r for r in res if r["unique_id"].startswith("model.")]
    out["bi_data_freshness"] = pd.DataFrame([{
        "pipeline_finished_utc": pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None),
        "data_start_date": pd.Timestamp(meta.get("start_date", "1970-01-01")), "data_end_date": pd.Timestamp(meta.get("end_date", "1970-01-01")),
        "is_synthetic": 1, "generator_seed": meta.get("seed"), "dbt_models_built": len(models),
        "dbt_tests_passed": sum(1 for r in tests if r["status"] == "pass"), "dbt_tests_failed": sum(1 for r in tests if r["status"] in ("fail", "error")),
        "data_label": "SYNTHETIC DATA - not real company performance"}])
    return out


def write_bi_tables(con, tables: dict[str, pd.DataFrame]) -> dict[str, int]:
    con.execute(f"create schema if not exists {BI_SCHEMA}")
    for name, df in tables.items():
        con.register("_bi_tmp", df)
        con.execute(f"create or replace table {BI_SCHEMA}.{name} as select * from _bi_tmp")
        con.unregister("_bi_tmp")
    return {k: len(v) for k, v in tables.items()}


# ----------------------------------------------------------------------------- exports (local fallback for any BI tool)
def export_csv(con, out_dir: Path | None = None) -> dict[str, int]:
    """Write every registry table to CSV (same names/columns as BigQuery) + _catalog.csv. Dates are ISO-8601."""
    out_dir = Path(out_dir or paths.BI_EXPORTS)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.csv"):
        old.unlink()
    counts, cat = {}, []
    for r in REGISTRY:
        df = con.sql(f"select * from {local_ref(r['name'])}").df()
        df.to_csv(out_dir / f"{r['name']}.csv", index=False)
        counts[r["name"]] = len(df)
        cat.append({"table": r["name"], "bigquery_dataset_suffix": r["layer"], "grain": r["grain"], "pages": r["pages"],
                    "date_field": r["date_field"] or "", "rows": len(df), "columns": len(df.columns)})
    pd.DataFrame(cat).to_csv(out_dir / "_catalog.csv", index=False)
    return counts


# ----------------------------------------------------------------------------- BigQuery publishing (UNVERIFIED live)
def publish_to_bigquery(con) -> dict[str, int]:
    """Load the Python-produced BI tables into <GP_BQ_DATASET>_analytics (WRITE_TRUNCATE). dbt builds the *_reporting dataset itself."""
    from google.cloud import bigquery
    from . import bigquery as bq
    s, client = bq.settings(), bq.client()
    ds_id = f"{s['project']}.{s['dataset']}_analytics"
    ds = bigquery.Dataset(ds_id)
    ds.location = s["location"]
    client.create_dataset(ds, exists_ok=True)
    counts = {}
    for r in REGISTRY:
        if r["layer"] != "analytics":
            continue
        df = con.sql(f"select * from {local_ref(r['name'])}").df()
        for c in df.columns:                     # BigQuery loads DATE objects fine; make bool-ish numpy types plain
            if df[c].dtype == bool:
                df[c] = df[c].astype("int64")
        job = client.load_table_from_dataframe(df, f"{ds_id}.{r['name']}",
                                               job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE"))
        job.result()
        counts[r["name"]] = len(df)
    return counts


# ----------------------------------------------------------------------------- Looker Studio data-source URLs (Linking API)
def looker_datasource_urls(project: str, dataset_prefix: str = "growthpulse") -> pd.DataFrame:
    """URLs that open Looker Studio and create a BigQuery TABLE data source for each registry table.
    Pattern documented in Google's Looker Studio Linking API (blank report + ds.ds0.* parameters). UNVERIFIED by the author."""
    from urllib.parse import urlencode
    rows = []
    for r in REGISTRY:
        dataset = f"{dataset_prefix}_{r['layer']}"
        q = {"ds.ds0.connector": "bigQuery", "ds.ds0.datasourceName": f"GP - {r['name']}", "ds.ds0.projectId": project,
             "ds.ds0.type": "TABLE", "ds.ds0.datasetId": dataset, "ds.ds0.tableId": r["name"]}
        rows.append({"table": r["name"], "dataset": dataset,
                     "url": "https://lookerstudio.google.com/reporting/create?" + urlencode(q)})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- field documentation
FIELD_DOC = {
    "metric_date": "Date the metric belongs to: spend date for spend, signup date for signups, first-paid date for customers/revenue",
    "week_start": "Monday of the week", "month_start": "First day of the month", "year_month": "Sortable text label YYYY-MM",
    "date_day": "Calendar day (primary key)", "acquisition_month": "Month of first payment (cohort of acquisition)",
    "attribution_model": "first_touch | last_touch | linear | position_based (rule-based credit, not causal)",
    "channel_name": "Marketing channel", "channel_label": "Channel name for display", "campaign_id": "Campaign key ('none' = no paid campaign)",
    "spend_usd": "Media spend (USD, platform-reported)", "impressions": "Ad impressions", "clicks": "Ad clicks", "paid_sessions": "Tracked website sessions from paid clicks",
    "signups": "Accounts created (credited fractionally under multi-touch models)", "trials": "Trials started", "new_customers": "New PAYING customers (first payment date)",
    "net_revenue_m3": "Net revenue (refunds netted) from the first 3 billing cycles", "net_revenue_m12": "Net revenue from the first 12 billing cycles",
    "net_revenue_to_date": "All net revenue collected so far from these customers",
    "is_eligible_m3": "1 if the 3-cycle window is fully observed for this date/month", "is_eligible_m12": "1 if the 12-cycle window is fully observed",
    "spend_eligible_m12": "Spend counted only for fully observed 12-cycle cohorts (denominator of censoring-safe ROAS/CAC)",
    "customers_eligible_m12": "New customers from fully observed 12-cycle cohorts", "revenue_m12_eligible": "12-cycle net revenue from fully observed cohorts",
    "gross_profit_m12_eligible": "revenue_m12_eligible x gross margin (ASSUMPTION 0.80)", "revenue_m3_eligible": "3-cycle net revenue from fully observed cohorts",
    "spend_eligible_m3": "Spend for fully observed 3-cycle cohorts", "customers_eligible_m3": "Customers from fully observed 3-cycle cohorts",
    "overhead_allocated_usd": "Non-media marketing cost allocated to the channel pro-rata to its share of paid spend",
    "overhead_eligible_m12": "Overhead for fully observed 12-cycle cohorts",
    "cac_paid_media": "Row-level paid-media CAC (NULL if no spend/customers). Do NOT average it - recompute SUM/SUM",
    "cac_fully_loaded": "Row-level fully loaded CAC", "roas_m3": "Row-level 3-cycle ROAS (NULL if cohort not fully observed)", "roas_m12": "Row-level 12-cycle ROAS",
    "revenue_ltv_m12": "12-cycle net revenue per new customer", "gross_profit_ltv_m12": "12-cycle gross profit per new customer", "cpc": "Cost per click",
    "visitors": "Visitors by first-visit date", "pricing_viewers": "Visitors who ever viewed pricing", "signup_starters": "Visitors who started signup",
    "paying_customers": "Visitors who became paying customers", "first_session_date": "Date of the visitor's first session",
    "cohort_month": "Month of first payment", "cohort_label": "YYYY-MM label of cohort_month", "months_since_start": "Billing cycle index (0 = first payment)",
    "cohort_size": "Customers in the cohort cell", "customers_observed": "Customers for whom this cycle could already have been billed",
    "customers_retained": "Of those, customers who paid in this cycle", "retention_rate": "customers_retained / customers_observed",
    "new_mrr_usd": "MMM outcome: first-payment revenue of subscriptions started that week", "spend_paid_search": "Weekly paid search spend",
    "spend_paid_social": "Weekly paid social spend", "spend_display": "Weekly display spend", "spend_affiliate": "Weekly affiliate spend",
    "spend_total": "Total weekly paid media spend", "promo_share": "Share of the week's days inside a promotion (MMM control)",
    "rate_control": "Conversion rate in control", "rate_treatment": "Conversion rate in treatment", "abs_lift": "Treatment minus control (percentage points as a fraction)",
    "rel_lift": "Relative lift = treatment/control - 1", "rel_lift_ci_low": "95% CI lower bound of relative lift", "rel_lift_ci_high": "95% CI upper bound of relative lift",
    "p_value": "Two-sided p-value", "significant": "True if p < planned alpha", "incremental_roas": "Incremental revenue / test spend (first-payment revenue)",
    "attributed_roas": "Revenue a last-touch report credits to the campaign / test spend", "verdict": "Plain-language reading of the result",
    "mde_relative": "Minimum detectable relative lift at 80% power with this sample", "experiment_type": "user-level holdout | geo holdout (DiD)",
    "share_of_revenue": "Estimated share of new MRR driven by the channel (MMM)", "share_p05": "5th percentile (90% interval lower)", "share_p95": "95th percentile (90% interval upper)",
    "avg_roi": "MMM average return: new MRR per $ of spend", "contribution_usd": "MMM-estimated new MRR attributable to the component",
    "component": "paid_search | paid_social | display | affiliate | baseline", "scenario": "Budget scenario name", "prob_better_than_current": "Share of bootstrap draws in which the plan beats the current mix",
    "calibration_factor": "Experiment-implied ROI / MMM ROI (bounded 0.25-4); diagnostic, not an automatic correction",
    "recommended_action": "Rule-based action (see methodology)", "rule_triggered": "The rule and threshold that produced the action",
    "is_synthetic": "1 = all data are simulated", "data_label": "Text to show on every page", "pipeline_finished_utc": "When the pipeline last finished (UTC)",
    "data_end_date": "Last day of data", "dbt_tests_passed": "dbt data tests passed in the last build", "dbt_tests_failed": "dbt data tests failed in the last build",
}
