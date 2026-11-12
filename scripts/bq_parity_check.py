#!/usr/bin/env python
"""After `dbt build --target bigquery`: confirm BigQuery reporting tables match the local DuckDB build (counts and key sums)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from growthpulse import bigquery as bq
try:
    df = bq.parity_check()
except bq.BigQueryConfigError as e:
    print("NOT CONFIGURED:", e); sys.exit(2)
print(df.to_string(index=False))
bad = df[~df.match]
print(f"\n{len(df) - len(bad)}/{len(df)} measures match")
sys.exit(1 if len(bad) else 0)
