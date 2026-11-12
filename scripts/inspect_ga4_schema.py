#!/usr/bin/env python
"""Print the ACTUAL GA4 sample schema from BigQuery INFORMATION_SCHEMA and flag columns the dbt models rely on that are missing."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from growthpulse import bigquery as bq
NEEDED = {"event_date", "event_timestamp", "event_name", "user_pseudo_id", "event_params", "traffic_source", "device", "geo", "ecommerce"}
try:
    df = bq.inspect_ga4_schema()
except bq.BigQueryConfigError as e:
    print("NOT CONFIGURED:", e); sys.exit(2)
print(df.to_string(index=False))
missing = NEEDED - set(df.column_name)
print("\nMISSING columns used by dbt models:", sorted(missing) if missing else "none")
sys.exit(1 if missing else 0)
