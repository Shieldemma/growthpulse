#!/usr/bin/env python
"""Copy marts built by dbt in BigQuery into the local DuckDB so the dashboard can display them (and export the GA4 funnel)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from growthpulse import bigquery as bq
try:
    print(bq.export_marts_to_duckdb())
except bq.BigQueryConfigError as e:
    print("NOT CONFIGURED:", e); sys.exit(2)
