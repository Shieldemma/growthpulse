# Local fallback: use the exported datasets in any BI tool (no cloud credentials)

`python scripts/run_pipeline.py` writes **27 CSV files + `_catalog.csv`** to `dashboard/bi_exports/`. They have exactly the same table names and columns as the BigQuery tables (`rpt_*`, `bi_*`), so every Looker Studio calculated field and DAX measure in this repo works on them unchanged. Dates are ISO `YYYY-MM-DD`, timestamps `YYYY-MM-DD HH:MM:SS`, flags 0/1.

| Tool | How | Caveats |
|---|---|---|
| **Looker Studio (no BigQuery)** | Create -> Data source -> **File Upload** (CSV) for each file, or upload to **Google Sheets** and use the Google Sheets connector | check Google's current file-size/row limits; uploads are static snapshots (re-upload after each pipeline run); set date fields to *Date* type |
| **Power BI Desktop (Windows)** | Get data -> Text/CSV, or Folder connector on `dashboard/bi_exports` | Desktop is Windows-only (see Power BI guide) |
| **Tableau / Excel / Google Sheets** | open the CSVs; relate on `channel_name`, `date_day`, `campaign_id` | Excel row limit ~1M is fine (largest file ~40k rows) |
| **DuckDB-aware tools** (DBeaver, VS Code SQL tools) | open `data/processed/growthpulse.duckdb` read-only; schemas `gp_reporting`, `gp_bi` | close the file in other tools before re-running the pipeline |
| **Python/R notebooks** | `pandas.read_csv("dashboard/bi_exports/rpt_marketing_daily.csv")` | |
| **Optional local viewer** | `streamlit run app/streamlit_app.py` — an exploratory app reading DuckDB; **not** the primary dashboard | kept for quick local checks |

To keep numbers consistent across tools always: sum metrics, compute ratios as ratio of sums, filter `rpt_attribution_monthly` to one `attribution_model` when summing spend, and use `*_eligible_*` columns for ROAS/LTV.

Verification: tests assert that the CSV set equals the registry (`tests/test_bi_layer.py`), that columns equal the DuckDB tables, and that totals reconcile to the marts.
