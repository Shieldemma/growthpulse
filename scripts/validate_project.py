#!/usr/bin/env python
"""Check that expected files, tables and outputs exist and key totals reconcile. Exit code 1 on any failure."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from growthpulse import validation
checks = validation.run_checks()
for c in checks:
    print(f"{c['status']:<5} {c['check']}" + (f"  [{c['detail']}]" if c["detail"] and c["status"] == "FAIL" else ""))
bad = [c for c in checks if c["status"] != "PASS"]
print(f"\n{len(checks) - len(bad)}/{len(checks)} checks passed")
sys.exit(1 if bad else 0)
