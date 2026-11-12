"""Data access for the dashboard. Every number shown comes from the DuckDB file built by the pipeline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from growthpulse import paths  # noqa: E402

DB = paths.DUCKDB_PATH


def db_ready() -> bool:
    if not DB.exists():
        return False
    try:
        con = duckdb.connect(str(DB), read_only=True)
        con.execute(f"select 1 from {paths.MARTS}.mart_marketing_performance limit 1")
        con.close()
        return True
    except Exception:  # noqa: BLE001
        return False


def require_data():
    """Stop the page with a friendly message if the pipeline has not been run."""
    if not db_ready():
        st.error("The analytical database was not found or is incomplete.")
        st.markdown(
            "Run the pipeline once from the project folder, then refresh this page:\n\n"
            "```bash\npython scripts/run_pipeline.py\n```\n"
            f"Expected file: `{DB}`")
        st.stop()


@st.cache_data(show_spinner=False, ttl=600)
def query(sql: str, _mtime: float = 0.0) -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()


def q(sql: str) -> pd.DataFrame:
    return query(sql, DB.stat().st_mtime if DB.exists() else 0.0)


def table(schema: str, name: str, where: str = "") -> pd.DataFrame:
    return q(f"select * from {schema}.{name} {where}")


def perf(model: str) -> pd.DataFrame:
    df = table(paths.MARTS, "mart_marketing_performance", f"where attribution_model = '{model}'")
    df["metric_date"] = pd.to_datetime(df["metric_date"])
    return df


def meta() -> dict:
    p = paths.DATA_RAW / "_generation_metadata.json"
    return json.loads(p.read_text()) if p.exists() else {}


def status() -> dict:
    return json.loads(paths.STATUS_JSON.read_text()) if paths.STATUS_JSON.exists() else {}


def dbt_results() -> list[dict]:
    p = paths.DATA_PROCESSED / "dbt_run_results.json"
    return json.loads(p.read_text()) if p.exists() else []
