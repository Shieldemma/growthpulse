#!/usr/bin/env python
"""Generate the SYNTHETIC datasets.   Usage: python scripts/generate_data.py [--seed 42] [--scale 1.0]"""
import argparse, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from growthpulse.datagen import GenConfig, generate, write_dataset
from growthpulse.paths import DATA_RAW

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--seed", type=int, default=42)
p.add_argument("--scale", type=float, default=1.0, help="traffic volume multiplier (0.15 = tiny/fast)")
p.add_argument("--out", type=Path, default=DATA_RAW)
a = p.parse_args()
t = time.time()
cfg = GenConfig(seed=a.seed, scale=a.scale)
tables = generate(cfg)
meta = write_dataset(tables, a.out, cfg)
print(f"Generated SYNTHETIC data in {time.time()-t:.1f}s -> {a.out}")
for k, v in meta["tables"].items():
    print(f"  {k:<28}{v['rows']:>10,} rows")
