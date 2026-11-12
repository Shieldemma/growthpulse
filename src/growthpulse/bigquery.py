"""OPTIONAL BigQuery integration (Mode B).

STATUS: implemented but UNVERIFIED against a live Google Cloud project (no credentials were available when this was
written). Every function here makes REAL API calls - none of them fakes a result. If credentials are missing they raise
a clear BigQueryConfigError instead of pretending.

Authentication (no secrets in the repo):
  * recommended: `gcloud auth application-default login`  (your own user login; nothing to store)
  * alternative: a service-account key file OUTSIDE this folder, referenced by GOOGLE_APPLICATION_CREDENTIALS
Environment variables: GCP_PROJECT_ID, GP_BQ_DATASET (default growthpulse), GP_BQ_RAW_DATASET (default growthpulse_raw),
GP_BQ_LOCATION (default US - the public GA4 sample lives in US, so your datasets must too).
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from . import paths
from .datagen import schema

GA4_TABLE = "bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*"
GA4_SCHEMA_PROBE_TABLE = "events_20210131"   # last shard of the documented sample range; change if it does not exist


class BigQueryConfigError(RuntimeError):
    """Raised for missing configuration/credentials (an actionable message, never a fake success)."""


def settings() -> dict:
    project = os.environ.get("GCP_PROJECT_ID", "").strip()
    if not project:
        raise BigQueryConfigError("GCP_PROJECT_ID is not set. Copy .env.example to .env, fill it in, and export it "
                                  "(see docs/bigquery_setup.md).")
    return {"project": project, "dataset": os.environ.get("GP_BQ_DATASET", "growthpulse"),
            "raw_dataset": os.environ.get("GP_BQ_RAW_DATASET", "growthpulse_raw"),
            "location": os.environ.get("GP_BQ_LOCATION", "US")}


def client(project: str | None = None):
    try:
        from google.cloud import bigquery
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError as e:  # pragma: no cover
        raise BigQueryConfigError("google-cloud-bigquery is not installed: pip install -r requirements.txt") from e
    s = settings()
    try:
        return bigquery.Client(project=project or s["project"], location=s["location"])
    except DefaultCredentialsError as e:
        raise BigQueryConfigError("No Google credentials found. Run `gcloud auth application-default login` "
                                  "(or set GOOGLE_APPLICATION_CREDENTIALS to a key file outside this repo).") from e


def bq_schema(table: str):
    from google.cloud import bigquery
    return [bigquery.SchemaField(c, schema.BQ_TYPE_MAP[t], mode="NULLABLE") for c, t, _ in schema.TABLES[table]["columns"]]


def check_connection() -> dict:
    """Runs two real calls: `select 1`, and a DRY-RUN (free) of the GA4 events query to report bytes that would be billed."""
    from google.cloud import bigquery
    c = client()
    c.query("select 1 as ok").result()
    cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    job = c.query(f"select count(*) from `{GA4_TABLE}` where _table_suffix between '20201101' and '20210131'", job_config=cfg)
    return {"project": c.project, "can_query": True, "ga4_full_scan_bytes_estimate": job.total_bytes_processed}


def inspect_ga4_schema(table: str = GA4_SCHEMA_PROBE_TABLE) -> pd.DataFrame:
    """Returns the ACTUAL column list of the GA4 sample (INFORMATION_SCHEMA), so models can be checked against reality."""
    c = client()
    sql = ("select column_name, data_type from `bigquery-public-data.ga4_obfuscated_sample_ecommerce.INFORMATION_SCHEMA.COLUMNS` "
           f"where table_name = '{table}' order by ordinal_position")
    return c.query(sql).to_dataframe()


def load_raw_to_bigquery(raw_dir: Path | None = None) -> dict[str, int]:
    """Create the raw dataset and load the SYNTHETIC CSVs (WRITE_TRUNCATE, so it is safe to re-run)."""
    from google.cloud import bigquery
    s, c = settings(), client()
    ds = bigquery.Dataset(f"{s['project']}.{s['raw_dataset']}")
    ds.location = s["location"]
    c.create_dataset(ds, exists_ok=True)
    raw_dir = Path(raw_dir or paths.DATA_RAW)
    counts = {}
    for t, spec in schema.TABLES.items():
        df = pd.read_csv(raw_dir / f"{t}.csv")
        for col, typ, _ in spec["columns"]:
            if typ == "DATE":
                df[col] = pd.to_datetime(df[col]).dt.date
            elif typ == "TIMESTAMP":
                df[col] = pd.to_datetime(df[col], utc=True)
        job = c.load_table_from_dataframe(df, f"{s['project']}.{s['raw_dataset']}.{t}",
                                          job_config=bigquery.LoadJobConfig(schema=bq_schema(t), write_disposition="WRITE_TRUNCATE"))
        job.result()
        counts[t] = len(df)
    return counts


def export_marts_to_duckdb(db_path: Path | None = None) -> dict[str, int]:
    """Copy the dbt marts built in BigQuery into the local DuckDB (schema gp_marts) so the dashboard can run on them,
    and write data/processed/ga4_funnel.csv from mart_ga4_funnel if it exists."""
    from . import warehouse
    s, c = settings(), client()
    tables = ["mart_marketing_performance", "mart_channel_unit_economics", "mart_customer_retention", "mart_growth_funnel",
              "mart_mmm_weekly", "mart_attribution_comparison", "dim_customers", "fct_payments", "fct_customer_revenue", "fct_marketing_spend"]
    con = warehouse.connect(db_path)
    counts = {}
    try:
        con.execute(f"create schema if not exists {paths.MARTS}")
        for t in tables:
            df = c.query(f"select * from `{s['project']}.{s['dataset']}_marts.{t}`").to_dataframe()
            con.register("_df", df)
            con.execute(f"create or replace table {paths.MARTS}.{t} as select * from _df")
            con.unregister("_df")
            counts[t] = len(df)
        try:
            g = c.query(f"""select 'Sessions' as step_label, sum(sessions) as sessions from `{s['project']}.{s['dataset']}_ga4.mart_ga4_funnel`
                            union all select 'Viewed item', sum(sessions_view_item) from `{s['project']}.{s['dataset']}_ga4.mart_ga4_funnel`
                            union all select 'Added to cart', sum(sessions_add_to_cart) from `{s['project']}.{s['dataset']}_ga4.mart_ga4_funnel`
                            union all select 'Began checkout', sum(sessions_begin_checkout) from `{s['project']}.{s['dataset']}_ga4.mart_ga4_funnel`
                            union all select 'Purchased', sum(sessions_purchase) from `{s['project']}.{s['dataset']}_ga4.mart_ga4_funnel`""").to_dataframe()
            g.to_csv(paths.DATA_PROCESSED / "ga4_funnel.csv", index=False)
            counts["ga4_funnel.csv"] = len(g)
        except Exception as e:  # noqa: BLE001
            counts["ga4_funnel.csv"] = f"skipped ({str(e).splitlines()[0]})"
    finally:
        con.close()
    return counts


def parity_check(db_path: Path | None = None) -> pd.DataFrame:
    """Compare the BI tables built LOCALLY (DuckDB) with the same tables built by dbt IN BigQuery: row counts and key sums.
    Same data + same SQL must give the same numbers; a mismatch means a dialect bug or stale data. UNVERIFIED live."""
    from . import warehouse
    s, c = settings(), client()
    con = warehouse.connect(db_path, read_only=True)
    checks = {"rpt_marketing_daily": ["spend_usd", "new_customers", "net_revenue_to_date"],
              "rpt_unit_economics_monthly": ["spend_usd", "overhead_allocated_usd", "new_customers"],
              "rpt_funnel_daily": ["visitors", "signups", "paying_customers"],
              "rpt_retention_cohort": ["customers_observed", "customers_retained", "net_revenue_usd"],
              "rpt_mmm_weekly": ["new_mrr_usd", "spend_total"], "rpt_customers": ["net_revenue_to_date_usd"]}
    rows = []
    try:
        for t, cols in checks.items():
            sel = ", ".join([f"count(*) as n_rows"] + [f"sum({x}) as {x}" for x in cols])
            local = con.sql(f"select {sel} from gp_reporting.{t}").df().iloc[0]
            cloud = c.query(f"select {sel} from `{s['project']}.{s['dataset']}_reporting.{t}`").to_dataframe().iloc[0]
            for k in local.index:
                lv, cv = float(local[k]), float(cloud[k])
                rows.append({"table": t, "measure": k, "local_duckdb": lv, "bigquery": cv, "match": abs(lv - cv) <= max(0.01, 1e-9 * abs(lv))})
    finally:
        con.close()
    return pd.DataFrame(rows)
