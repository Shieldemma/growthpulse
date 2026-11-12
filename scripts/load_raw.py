#!/usr/bin/env python
"""Load data/raw/*.csv into the local DuckDB file (schema `raw`)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from growthpulse import warehouse
counts = warehouse.load_raw()
for k, v in counts.items():
    print(f"  raw.{k:<28}{v:>10,}")
