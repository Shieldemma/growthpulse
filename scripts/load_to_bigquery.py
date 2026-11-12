#!/usr/bin/env python
"""Load the SYNTHETIC raw CSVs into BigQuery (dataset GP_BQ_RAW_DATASET). Re-runnable."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from growthpulse import bigquery as bq
try:
    counts = bq.load_raw_to_bigquery()
except bq.BigQueryConfigError as e:
    print("NOT CONFIGURED:", e); sys.exit(2)
for k, v in counts.items():
    print(f"  {k:<28}{v:>10,}")
