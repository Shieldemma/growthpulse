"""Local warehouse helpers: load raw CSVs into DuckDB, run dbt, open read-only connections."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import duckdb

from . import paths
from .datagen import schema


def connect(db_path: Path | str | None = None, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    p = Path(db_path or paths.DUCKDB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(p), read_only=read_only)


def load_raw(raw_dir: Path | str | None = None, db_path: Path | str | None = None) -> dict[str, int]:
    """Load every raw CSV into DuckDB schema `raw` with explicit column types. Returns row counts."""
    raw_dir = Path(raw_dir or paths.DATA_RAW)
    missing = [t for t in schema.TABLES if not (raw_dir / f"{t}.csv").exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing raw CSVs in {raw_dir}: {missing}. Run `python scripts/generate_data.py` first.")
    con = connect(db_path)
    counts = {}
    try:
        con.execute(f"create schema if not exists {paths.RAW_SCHEMA}")
        for t, spec in schema.TABLES.items():
            cols = ", ".join(f"'{c}': '{typ}'" for c, typ, _ in spec["columns"])
            con.execute(
                f"create or replace table {paths.RAW_SCHEMA}.{t} as "
                f"select * from read_csv('{(raw_dir / (t + '.csv')).as_posix()}', header=true, columns={{{cols}}})")
            counts[t] = con.execute(f"select count(*) from {paths.RAW_SCHEMA}.{t}").fetchone()[0]
    finally:
        con.close()
    return counts


def data_end_date(raw_dir: Path | str | None = None) -> str:
    meta = json.loads((Path(raw_dir or paths.DATA_RAW) / "_generation_metadata.json").read_text())
    return meta["end_date"]


def run_dbt(command: list[str], target: str = "duckdb", db_path: Path | str | None = None,
            end_date: str | None = None, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a dbt command inside dbt_project/ (e.g. ['build'] or ['docs', 'generate'])."""
    env = os.environ.copy()
    env["DBT_TARGET"] = target
    env["GP_DUCKDB_PATH"] = str(Path(db_path or paths.DUCKDB_PATH).resolve())
    env["DBT_PROFILES_DIR"] = str(paths.DBT_DIR)
    env.setdefault("DBT_SEND_ANONYMOUS_USAGE_STATS", "False")
    cmd = [sys.executable, "-m", "dbt.cli.main", *command]
    if command[0] in {"build", "run", "test", "compile", "docs", "seed", "parse"} and end_date:
        cmd += ["--vars", json.dumps({"data_end_date": end_date})]
    return subprocess.run(cmd, cwd=paths.DBT_DIR, env=env, text=True, capture_output=capture)


def dbt_results(project_dir: Path | None = None) -> list[dict]:
    """Parse dbt's target/run_results.json into a flat list (used by the Data Quality page)."""
    p = (project_dir or paths.DBT_DIR) / "target" / "run_results.json"
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return [{"unique_id": r["unique_id"], "status": r["status"],
             "execution_time_s": round(r.get("execution_time", 0), 3),
             "failures": r.get("failures"), "message": r.get("message")} for r in data.get("results", [])]
