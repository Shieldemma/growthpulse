#!/usr/bin/env python
"""Step 1 of BigQuery mode: verify authentication and show the estimated scan size of the GA4 sample (dry run, no charge)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from growthpulse import bigquery as bq
try:
    r = bq.check_connection()
except bq.BigQueryConfigError as e:
    print("NOT CONFIGURED:", e); sys.exit(2)
print(r, f"\nGA4 full-range scan would process about {r['ga4_full_scan_bytes_estimate'] / 1e9:.2f} GB (the first 1 TB/month of queries is free on-demand).")
