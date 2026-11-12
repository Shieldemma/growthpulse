"""Validation: do all expected files, tables and outputs exist, and do key numbers reconcile?
Run: python scripts/validate_project.py   (exit code 0 = all checks passed)."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from . import bi, paths
from .datagen import schema

EXPECTED_TABLES = {
    paths.STAGING: ["stg_channels", "stg_campaigns", "stg_ad_spend", "stg_overhead", "stg_promotions", "stg_plans", "stg_sessions",
                    "stg_events", "stg_customers", "stg_subscriptions", "stg_payments", "stg_refunds",
                    "stg_experiment_catalog", "stg_experiment_assignments"],
    paths.INTERMEDIATE: ["int_sessions", "int_visitors", "int_customer_acquisition", "int_touchpoints",
                         "int_attribution_credit", "int_month_index"],
    paths.MARTS: ["fct_payments", "fct_customer_revenue", "fct_marketing_spend", "dim_customers", "mart_marketing_performance",
                  "mart_channel_unit_economics", "mart_customer_retention", "mart_growth_funnel", "mart_mmm_weekly",
                  "mart_attribution_comparison"],
    paths.ANALYTICS: ["experiment_results", "experiment_balance", "experiment_contamination", "mmm_fit", "mmm_model_comparison",
                      "mmm_channel_summary", "mmm_contrib_weekly", "mmm_budget_scenarios", "mmm_response_curves",
                      "mmm_diagnostics", "mmm_sensitivity", "mmm_params", "mmm_meta", "recommendations", "channel_economics",
                      "geo_lift_results", "geo_lift_weekly", "lifecycle_results", "lifecycle_value", "mmm_calibration"],
    "gp_reporting": [r["name"] for r in bi.REGISTRY if r["layer"] == "reporting"],
    "gp_bi": [r["name"] for r in bi.REGISTRY if r["layer"] == "analytics"],
}


def run_checks(db_path: Path | None = None, raw_dir: Path | None = None, root: Path | None = None,
               report_path: Path | None = None, export_dir: Path | None = None) -> list[dict]:
    root = Path(root or paths.ROOT)
    raw_dir = Path(raw_dir or paths.DATA_RAW)
    db_path = Path(db_path or paths.DUCKDB_PATH)
    out: list[dict] = []

    def add(name, ok, detail=""):
        out.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    for t in schema.TABLES:
        add(f"raw csv exists: {t}.csv", (raw_dir / f"{t}.csv").exists())
    add("generation metadata exists", (raw_dir / "_generation_metadata.json").exists())
    rp = Path(report_path) if report_path else root / "reports" / "business_report.md"
    add("output exists: business report", rp.exists(), str(rp))
    add("output exists: weekly insight brief", (rp.parent / "weekly_insight_brief.md").exists())
    ed = Path(export_dir) if export_dir else root / "dashboard" / "bi_exports"
    add("BI CSV exports exist (all registry tables + catalog)", len(list(ed.glob("*.csv"))) >= len(bi.REGISTRY) + 1, str(ed))
    if not db_path.exists():
        add("duckdb file exists", False, str(db_path))
        return out
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        for sch, tables in EXPECTED_TABLES.items():
            for t in tables:
                try:
                    n = con.execute(f"select count(*) from {sch}.{t}").fetchone()[0]
                    add(f"table {sch}.{t} has rows", n > 0, f"{n:,} rows")
                except Exception as e:  # noqa: BLE001
                    add(f"table {sch}.{t} has rows", False, str(e).splitlines()[0])
        q = lambda s: con.execute(s).fetchone()[0]
        try:
            add("raw spend == mart spend (first_touch)",
                abs(q(f"select sum(spend_usd) from {paths.RAW_SCHEMA}.ad_spend_daily") -
                    q(f"select sum(spend_usd) from {paths.MARTS}.mart_marketing_performance where attribution_model='first_touch'")) < 0.01)
            add("raw net revenue == fct_payments net",
                abs(q(f"select sum(gross_amount_usd) from {paths.RAW_SCHEMA}.payments") - q(f"select coalesce(sum(refund_amount_usd),0) from {paths.RAW_SCHEMA}.refunds")
                    - q(f"select sum(net_amount_usd) from {paths.MARTS}.fct_payments")) < 0.01)
            add("paying customers == subscriptions",
                q(f"select count(*) from {paths.MARTS}.dim_customers where is_paying=1") == q(f"select count(*) from {paths.RAW_SCHEMA}.subscriptions"))
        except Exception as e:  # noqa: BLE001
            add("reconciliation checks", False, str(e).splitlines()[0])
    finally:
        con.close()
    return out
