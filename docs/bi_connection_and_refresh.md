# BI connection, refresh, caching, credentials and cost guide

> **Verification status.** Everything about BigQuery, dbt on BigQuery, Looker Studio and Power BI Service below is **documented behaviour plus untested configuration**: the author had no Google Cloud, Looker Studio or Power BI accounts. Statements marked (docs) were checked against Google's / Microsoft's public documentation on the date this was written; **re-check pricing and UI**, they change. Local mode (DuckDB + CSV) is fully tested.

## 1. How data flows, and who refreshes what
```
generate/load (python) ─► BigQuery raw ─► dbt build ─► <ds>_reporting (rpt_*)  ─┐
python analytics (local) ─► publish script ─► <ds>_analytics (bi_*)             ├─► Looker Studio / Power BI
                                                                                 └─► CSV exports (local fallback)
```
Nothing refreshes by itself: **dbt only runs when you (or a scheduler) run it**, Python analytics only when you run the pipeline, and the BI tool only re-queries when its cache expires. A "stale dashboard" is therefore one of three different problems (section 7).

## 2. Live vs imported vs cached — exact meanings
| Mode | Where it applies | What is actually stored | Freshness | Cost |
|---|---|---|---|---|
| **Live query (direct)** | Looker Studio BigQuery connector (every chart sends a SQL query when its cache is empty); Power BI **DirectQuery** | Nothing in the BI tool except Looker Studio's short-lived result cache | Newest BigQuery data at query time | Every uncached query scans bytes in BigQuery |
| **Cached live query** | Looker Studio **data freshness** setting (docs: default 12 h for BigQuery; results reused until the threshold passes; "Refresh data" forces a re-query). Also BigQuery's own result cache for identical queries (typically 24 h if the table is unchanged) | Query results in memory | Up to the freshness window old | Cache hits are free |
| **Imported snapshot** | Power BI **Import** mode; Looker Studio **Extract Data** connector | A copy of the data inside the BI tool | As old as the last scheduled/manual refresh | Cost only at refresh time |
| **Static file** | CSV/Google Sheets/upload (local fallback) | The file contents | As old as the file | none |

Looker Studio specifics (docs): with **Owner's credentials** every viewer shares one freshness setting and one cache — "a single data freshness setting" for the report; with **Viewer's credentials** each viewer has their own. Normal BigQuery query costs apply whenever Looker Studio queries the project.

## 3. Credentials and access control
| Decision | Recommendation for this portfolio | Why / risk |
|---|---|---|
| dbt -> BigQuery | `gcloud auth application-default login` locally; **Workload Identity Federation** in GitHub Actions (no key file) | no secrets in the repo |
| Looker Studio data credentials | **Owner's credentials** on a dedicated project containing only synthetic data | viewers need no Google Cloud access, but all viewer queries bill to the owner and any viewer can see all table data |
| Private/company data | **Viewer's credentials** | each viewer needs `roles/bigquery.dataViewer` on the datasets and `roles/bigquery.jobUser` on a billing project |
| Dataset access | Grant the Looker/Power BI identity **read-only** on `*_reporting` and `*_analytics` only; never on `*_raw` | least privilege |
| Public sharing | "Anyone with the link" only for synthetic data; never share BigQuery datasets publicly | |
| Service accounts | one for dbt (`BigQuery Data Editor` + `Job User`), none shared with BI viewers; keys outside the repo or none at all | |
| Rotate/revoke | Remove a leaked key immediately in Console -> IAM -> Service accounts -> Keys | |

## 4. Costs and billing precautions
* Looker Studio itself is free; **BigQuery query bytes** are what you pay for (on-demand; free monthly query tier exists — check the current pricing page). The BI tables are tiny (tens of KB to a few MB each; `dashboard/bi_exports/_catalog.csv` lists row counts), and BigQuery bills a minimum per table scanned per query (docs: 10 MB on-demand), so a page with ~15 charts is a few hundred MB scanned per uncached refresh at most — fractions of a cent, but **blended data sources, custom SQL and very short freshness windows multiply this**.
* Controls: (1) set data freshness to 12 h or longer in production; (2) connect to the pre-aggregated `rpt_*` / `bi_*` tables, **not** to raw or staging; (3) avoid Looker Studio "custom query" connections and blends on big tables; (4) keep dbt's `maximum_bytes_billed` (10 GB default here); (5) in Google Cloud set a **budget alert** and a **custom daily query quota** for the project; (6) use a dedicated project for the portfolio; (7) delete datasets when finished.
* BI Engine (paid in-memory acceleration) is unnecessary at this size.
* Power BI Import makes refresh the only BigQuery cost; DirectQuery sends queries on every interaction.

## 5. Running dbt: manual or scheduled
| Option | How | Notes |
|---|---|---|
| Manual (default) | `set -a; source .env; set +a; bash scripts/refresh_bigquery.sh` | runs local pipeline -> loads raw -> `dbt build` on BigQuery -> publishes `bi_*` -> parity check |
| GitHub Actions | `.github/workflows/refresh-bigquery.yml` (manual button + weekly cron) | needs Workload Identity Federation set up once; **unverified** |
| cron/launchd on your Mac | `crontab -e` -> `0 6 * * 1 cd ~/Documents/growthpulse && . .venv/bin/activate && set -a && . .env && set +a && bash scripts/refresh_bigquery.sh >> logs/refresh.log 2>&1` | the Mac must be awake; fine for a portfolio, not for production |
| dbt Cloud | connect the repo, add a BigQuery connection and a scheduled job | free plan limits change — check dbt's pricing page |
| Production pattern | Cloud Run job + Cloud Scheduler (or Airflow/Dagster) running `dbt build`; BigQuery scheduled queries for tiny SQL jobs | not included |
The Python analytics (MMM, experiments) currently run **locally on the DuckDB copy** and are *published* to BigQuery; they are not computed inside BigQuery. Because the synthetic data and SQL are identical, `scripts/bq_parity_check.py` should report all measures matching.

## 6. Data freshness end to end
| Stage | Latency | How to see it |
|---|---|---|
| Source data | static synthetic data (a real source would be streamed/loaded) | `bi_data_freshness.data_end_date` |
| dbt | only when run | `bi_data_freshness.pipeline_finished_utc`; dbt run logs |
| BigQuery result cache | up to 24 h for identical queries if tables unchanged (a dbt rebuild changes the tables and invalidates it) | |
| Looker Studio cache | default 12 h; *Refresh data* button (viewer menu) or lower the freshness setting (data source -> *Data freshness*) | |
| Power BI Import | until next refresh (Service -> semantic model -> *Refresh now* / schedule) | |

## 7. Troubleshooting stale data and failed refreshes
| Symptom | Likely cause | Check / fix |
|---|---|---|
| Dashboard numbers did not change after `dbt build` | Looker Studio cache | click *Refresh data*; lower freshness to 15 min–1 h while testing; hard-refresh the browser |
| `pipeline_finished_utc` is old | `publish_analytics_to_bigquery.py` not re-run (dbt only updates `rpt_*`) | run `bash scripts/refresh_bigquery.sh` |
| Page 8 shows `dbt_tests_failed > 0` | a data test failed in the last run | read `dbt_project/target/run_results.json`; fix data/logic; rerun |
| New column missing in a chart | Looker Studio kept the old schema | data source -> *Reconnect / Refresh fields*; for Power BI *Refresh preview* in Power Query |
| Looker: "Data Set Configuration Error" / permission | owner lost access or the table was dropped/renamed | open the data source, re-authorise; confirm the table exists; IAM roles in section 3 |
| Looker works for you, blank/denied for viewers | data source uses Viewer's credentials and viewers lack BigQuery access | switch to Owner's credentials (synthetic data only) or grant roles |
| Charts empty after a rebuild | `dbt build` replaced tables while queries ran, or wrong dataset location | retry; keep all datasets in `US` |
| Numbers differ between Looker and the CSV | date range/filters, attribution model, or ratio computed as an average | use ratio-of-sums calculated fields; compare with `bq_parity_check.py` |
| dbt on BigQuery: `Query exceeded limit for bytes billed` | `maximum_bytes_billed` guard | raise `GP_BQ_MAX_BYTES_BILLED` deliberately or shrink the GA4 date vars |
| dbt: `Access Denied` / `Not found: Dataset ... in location` | IAM or region mismatch | roles `BigQuery Data Editor`, `Job User`, `User`; all datasets in `GP_BQ_LOCATION` (US) |
| GitHub Action fails at auth | Workload Identity Federation not configured | follow Google's WIF guide; set the three repo variables |
| Power BI scheduled refresh times out | large import or credentials expired | import fewer/smaller tables (`rpt_funnel_daily` and `rpt_customers` are the largest), re-enter credentials, check the BigQuery connector notes in Microsoft docs |
| Power BI DirectQuery slow | each visual sends a query | switch to Import for this small dataset |

## 8. Local fallback
See `docs/local_fallback_bi.md` — identical tables as CSV in `dashboard/bi_exports/` need no cloud account.
