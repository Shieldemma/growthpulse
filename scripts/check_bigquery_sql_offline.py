#!/usr/bin/env python
"""OFFLINE sanity check of the BigQuery side of the dbt project (needs NO Google account).

1. Compiles every model with the BigQuery adapter with a stubbed connection (no credentials, no network).
2. Parses each compiled SQL file with sqlglot's BigQuery dialect.

This proves the Jinja renders and the SQL is syntactically valid BigQuery. It does NOT prove the queries run, return
the right numbers, or that table/column names exist in Google's datasets - that needs real credentials
(see docs/bigquery_setup.md).
"""
import glob, os, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.update(DBT_PROFILES_DIR=str(ROOT / "dbt_project"), DBT_TARGET="bigquery", GCP_PROJECT_ID="offline-check",
                  DBT_SEND_ANONYMOUS_USAGE_STATS="False", GP_DUCKDB_PATH=str(ROOT / "data/processed/growthpulse.duckdb"))
os.chdir(ROOT / "dbt_project")

# Replace the BigQuery connection opener with a stub so dbt never tries to reach Google (compile needs no warehouse).
from dbt.adapters.bigquery import connections as _bq
from dbt.adapters.contracts.connection import ConnectionState


class _Handle:           # minimal stand-in for a BigQuery client
    def close(self):
        pass

    def __getattr__(self, name):          # any client call (list_tables, get_dataset, ...) returns "nothing exists"
        return lambda *a, **k: []


def _fake_open(cls, connection):
    connection.handle = _Handle()
    connection.state = ConnectionState.OPEN
    return connection


_bq.BigQueryConnectionManager.open = classmethod(_fake_open)

import json
from dbt.cli.main import dbtRunner
shutil.rmtree("target/compiled", ignore_errors=True)
res = dbtRunner().invoke(["compile", "--no-introspect", "--vars", json.dumps({"data_end_date": "2025-12-28"})])
if not res.success:
    print("dbt compile FAILED:", res.exception); sys.exit(1)

import sqlglot
from sqlglot.errors import ParseError
ok = bad = 0
for f in sorted(glob.glob("target/compiled/growthpulse/models/**/*.sql", recursive=True)):
    try:
        sqlglot.parse(open(f).read(), read="bigquery"); ok += 1
    except ParseError as e:
        bad += 1; print("PARSE ERROR", f, str(e)[:300])
print(f"compiled + BigQuery-syntax-parsed: {ok} ok, {bad} failed (model SQL and generated test SQL under models/)")
sys.exit(1 if bad or ok == 0 else 0)
