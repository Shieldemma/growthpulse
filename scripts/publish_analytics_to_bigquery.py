#!/usr/bin/env python
"""Publish the Python-produced BI tables (experiments, geo-lift, lifecycle, MMM, recommendations, freshness) to BigQuery
dataset <GP_BQ_DATASET>_analytics. Run `python scripts/run_pipeline.py` first. UNVERIFIED against live BigQuery."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from growthpulse import bi, bigquery as bq, warehouse
try:
    con = warehouse.connect(read_only=True)
    counts = bi.publish_to_bigquery(con)
except bq.BigQueryConfigError as e:
    print("NOT CONFIGURED:", e); sys.exit(2)
for k, v in counts.items():
    print(f"  {k:<28}{v:>8,} rows")
