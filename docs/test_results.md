# Test results of the final build

Environment: Linux (x86_64), Python 3.12.3 and 3.13, versions in `requirements.txt`. Last full re-run: 12 Nov 2026 (`run_pipeline.py --regenerate`: 102/102 validation checks; `pytest`: 129 passed). Regenerated BI exports matched the previous run to within floating-point noise.

| Check | Command | Result |
|---|---|---|
| Full pytest suite | `python -m pytest -v` | **129 passed, 0 failed, 0 skipped** (108 s) |
| - per file | | dashboard smoke 14 · attribution 24 · BI layer 13 · BigQuery-offline 5 · data generation 14 · experiments 12 · geo-lift/lifecycle/calibration/insights 8 · metrics 18 · MMM 13 · pipeline integration 8 |
| dbt on DuckDB | `dbt build` (via `run_pipeline.py`) | **44 models built, 135/135 dbt tests passed** |
| Validation script | `python scripts/validate_project.py` | **102/102 checks passed** (raw CSVs, 18 warehouse layers' tables, 27 BI tables, 28 BI CSVs, reports, reconciliations) |
| Clean rebuild | wipe generated artefacts, `run_pipeline.py --regenerate` | succeeds in about 1 minute; regenerated CSVs identical SHA-256 (the original 14 tables are unchanged by the added experiment tables) |
| BigQuery models, offline | `python scripts/check_bigquery_sql_offline.py` | 179 compiled SQL files (all models incl. the 10 `rpt_*` and GA4 models, plus generated test SQL) parsed as BigQuery SQL, 0 failures |
| Optional Streamlit viewer | `streamlit run app/streamlit_app.py --server.headless true` | server started (HTTP 200, health ok) earlier in the build; all 10 pages render in headless tests |
| `dbt docs generate` | in `dbt_project/` | succeeded |

## Could NOT be run (and why)
| Item | Reason | How you can verify |
|---|---|---|
| **Looker Studio report** (creation, data sources, calculated fields, filters, sharing) | needs your Google account; no API creates report pages. Calculated-field formulas were checked only against the real column names (test), not executed in Looker Studio | `docs/looker_studio/README.md`; compare numbers with `dashboard/bi_exports/` and `reports/business_report.md` |
| Looker Studio one-click links (`docs/looker_studio/datasource_links.md`) | built from Google's documented Linking API pattern (URL structure unit-tested); never clicked | regenerate with your project id and click |
| Any live BigQuery call: `dbt run/test` on BigQuery, GA4 models, `load_to_bigquery.py`, `publish_analytics_to_bigquery.py`, `bq_parity_check.py`, `refresh_bigquery.sh` | no Google Cloud credentials / network access | `docs/bigquery_setup.md`, `docs/bi_connection_and_refresh.md` |
| GitHub Actions workflow | never executed; needs Workload Identity Federation | enable it after configuring the three repository variables |
| Power BI model, DAX, refresh | Power BI Desktop is Windows-only; no account | `dashboard/powerbi/README.md` |
| macOS-specific behaviour (`setup_mac.sh`, Homebrew) | built on Linux | `docs/setup_macos.md`, `docs/troubleshooting.md` |

## Known warnings
* dbt prints `MissingArgumentsPropertyInGenericTestDeprecation` (newer dbt prefers an `arguments:` key under generic tests). Tests still run and pass.
* MMM diagnostics flag residual autocorrelation; reported in the business report and the Looker/Power BI specs rather than hidden.
* The geo-lift generator has small geo-specific drift, so the pre-period placebo is occasionally sizeable for unlucky seeds; the analysis reports it (`parallel_trends_ok`) instead of assuming parallel trends.
