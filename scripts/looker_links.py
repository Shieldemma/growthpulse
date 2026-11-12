#!/usr/bin/env python
"""Print / save one-click Looker Studio links that create a BigQuery data source for every GrowthPulse BI table.
Usage:  python scripts/looker_links.py [--project MY_PROJECT] [--dataset growthpulse]  ->  docs/looker_studio/datasource_links.md
Each link opens Looker Studio and asks you to confirm/authorise the data source (Google's Linking API). Nothing is created without your click."""
import argparse, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from growthpulse import bi
p = argparse.ArgumentParser()
p.add_argument("--project", default=os.environ.get("GCP_PROJECT_ID", "YOUR_PROJECT_ID"))
p.add_argument("--dataset", default=os.environ.get("GP_BQ_DATASET", "growthpulse"))
a = p.parse_args()
df = bi.looker_datasource_urls(a.project, a.dataset)
out = ROOT / "docs" / "looker_studio" / "datasource_links.md"
out.parent.mkdir(parents=True, exist_ok=True)
lines = [f"# One-click Looker Studio data-source links\n", f"Project `{a.project}`, dataset prefix `{a.dataset}`. **UNVERIFIED** (built from Google's documented Linking API pattern; no Google account was available to click them).\n",
         "Regenerate with your own project: `python scripts/looker_links.py --project YOUR_PROJECT_ID`.\n", "| Table | Dataset | Link |", "|---|---|---|"]
lines += [f"| `{r.table}` | `{r.dataset}` | [create data source]({r.url}) |" for r in df.itertuples()]
out.write_text("\n".join(lines) + "\n")
print(f"wrote {out}  ({len(df)} links, project={a.project})")
