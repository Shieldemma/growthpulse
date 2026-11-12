#!/usr/bin/env python
"""Run the whole Local Demo Mode pipeline.
   python scripts/run_pipeline.py                 # reuse CSVs if present
   python scripts/run_pipeline.py --regenerate    # rebuild synthetic data first
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from growthpulse import pipeline

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
p.add_argument("--regenerate", action="store_true")
p.add_argument("--seed", type=int, default=42)
p.add_argument("--scale", type=float, default=1.0)
p.add_argument("--n-boot", type=int, default=300)
a = p.parse_args()
res = pipeline.run(regenerate=a.regenerate, seed=a.seed, scale=a.scale, n_boot=a.n_boot)
bad = [c for c in res["checks"] if c["status"] != "PASS"]
if not bad:  # refresh the static web dashboard (docs/index.html) from the new BI exports
    import subprocess
    subprocess.run([sys.executable, str(Path(__file__).with_name("build_web_dashboard.py"))], check=False)
print(f"\nValidation: {len(res['checks']) - len(bad)}/{len(res['checks'])} checks passed")
for c in bad:
    print("  FAIL:", c["check"], c["detail"])
print("Next: open docs/index.html (web dashboard) or run: streamlit run app/streamlit_app.py" if not bad else "Fix the failures above, then re-run.")
sys.exit(1 if bad else 0)
