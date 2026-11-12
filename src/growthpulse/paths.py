"""Central place for project paths so no module hardcodes a location."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(os.environ.get("GROWTHPULSE_HOME", Path(__file__).resolve().parents[2]))
DATA_RAW = Path(os.environ.get("GP_RAW_DIR", ROOT / "data" / "raw"))
DATA_PROCESSED = Path(os.environ.get("GP_PROCESSED_DIR", ROOT / "data" / "processed"))
DUCKDB_PATH = Path(os.environ.get("GP_DUCKDB_PATH", DATA_PROCESSED / "growthpulse.duckdb"))
DBT_DIR = ROOT / "dbt_project"
REPORTS = ROOT / "reports"
BI_EXPORTS = Path(os.environ.get("GP_BI_EXPORT_DIR", ROOT / "dashboard" / "bi_exports"))
POWERBI_EXPORTS = BI_EXPORTS   # backwards-compatible alias
STATUS_JSON = DATA_PROCESSED / "pipeline_status.json"

# Schemas inside the DuckDB file (mirror BigQuery dataset names: <prefix>_<layer>)
RAW_SCHEMA = "raw"
STAGING = "gp_staging"
INTERMEDIATE = "gp_intermediate"
MARTS = "gp_marts"
ANALYTICS = "gp_analytics"   # tables written by Python (experiments, MMM, report inputs)
