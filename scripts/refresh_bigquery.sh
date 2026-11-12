#!/usr/bin/env bash
# Manual BigQuery refresh (everything the dashboard needs). Run from the project folder with .venv active and .env loaded:
#   set -a; source .env; set +a; bash scripts/refresh_bigquery.sh
# Steps stop at the first error. UNVERIFIED against live BigQuery - read docs/bi_connection_and_refresh.md first.
set -euo pipefail
: "${GCP_PROJECT_ID:?GCP_PROJECT_ID is not set (see .env.example)}"

echo "[1/6] Local pipeline (synthetic data, DuckDB, Python analytics, BI CSVs)"
python scripts/run_pipeline.py
echo "[2/6] Load raw synthetic tables to BigQuery"
python scripts/load_to_bigquery.py
echo "[3/6] dbt build on BigQuery (models + tests)"
( cd dbt_project && DBT_PROFILES_DIR=. DBT_TARGET=bigquery dbt build --vars "{\"data_end_date\": \"$(python -c "import json;print(json.load(open('../data/raw/_generation_metadata.json'))['end_date'])")\"}" )
echo "[4/6] Publish Python analytics tables to BigQuery"
python scripts/publish_analytics_to_bigquery.py
echo "[5/6] Parity check: BigQuery vs local DuckDB"
python scripts/bq_parity_check.py
echo "[6/6] Done. Looker Studio will show new data after its data-freshness window expires (default 12 h) or after you click Refresh data."
