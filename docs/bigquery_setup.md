# BigQuery + dbt mode (optional cloud integration)

> **STATUS: implemented, syntax-checked offline, NOT executed against live BigQuery.** No Google Cloud credentials were available when this project was built, so no cloud query has been run by the author. What *was* verified: all models compile with the BigQuery adapter and every compiled file parses as BigQuery SQL (`python scripts/check_bigquery_sql_offline.py`); the synthetic-data models are identical SQL to those verified on DuckDB. What is **unverified**: authentication, permissions, that the GA4 sample's columns match the models, the incremental `insert_overwrite` logic, and cost estimates. Follow the steps below; each has a command that tells you honestly whether it worked.

## What BigQuery mode adds
| Part | Data | Notes |
|---|---|---|
| Synthetic SaaS marts | the same synthetic CSVs, loaded to BigQuery | same dbt models as local mode |
| GA4 models (`models/ga4/`) | **real** public sample `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*` (Google Merchandise Store, documented range 2020-11-01 to 2021-01-31) | funnel + order revenue by first-user source. **No ad cost, no subscriptions** -> no CAC/LTV/ROAS from GA4 |

GA4 columns used (from Google's documented export schema; confirm with step 5): `event_date` (STRING YYYYMMDD), `event_timestamp` (INT64 microseconds), `event_name`, `user_pseudo_id`, `event_params` (REPEATED key + value.int_value/string_value), `traffic_source.{source,medium,name}` (user-level first acquisition), `device.category`, `geo.country`, `ecommerce.{transaction_id, purchase_revenue_in_usd}`.

## Costs and billing (read first)
* BigQuery charges for bytes **scanned** by queries (on-demand pricing; the first 1 TiB per month is free at the time of writing - verify on Google's pricing page) and for stored data beyond the free tier. Reading the public GA4 sample counts as scanning, the public dataset's storage is free to you.
* The synthetic data are small (< 200 MB). The GA4 sample is also small (hundreds of MB to ~1 GB for the full range). `scripts/bq_check.py` prints a **dry-run estimate** (free) before you run anything.
* dbt is configured with `maximum_bytes_billed` (default 10 GB, env `GP_BQ_MAX_BYTES_BILLED`): any single query that would scan more fails instead of billing you.
* Use a project with a **budget alert** (Billing -> Budgets & alerts). Delete the datasets when finished (step 9).
* The BigQuery sandbox (no billing account) allows queries and 10 GB storage, but tables expire after 60 days and some features are limited; if loading fails with a billing error, enable billing on a project with a budget alert.

## Permissions
Your user needs on the project: `BigQuery Job User` (run queries), `BigQuery Data Editor` (create/overwrite tables) and `BigQuery User` (create datasets). The public dataset needs no extra permission.

## Safe credential management
* **Best: no key file at all.** Use your own login: `gcloud auth application-default login`. Credentials are stored by gcloud in your home folder, outside the repo.
* If you must use a service account: create it with only the roles above, download the key to a folder **outside** the project (e.g. `~/.secrets/`), and point `GOOGLE_APPLICATION_CREDENTIALS` at it. Never paste keys into code, `.env.example`, notebooks, chats or commits.
* `.gitignore` blocks `.env`, `*credentials*.json`, `*service-account*.json`, `*.pem`. A test (`tests/test_bigquery_code.py`) checks that no key material appears in the committed config.
* If a key ever leaks: delete it in Google Cloud Console -> IAM -> Service Accounts -> Keys, immediately.

## Steps
1. **Create a project** at https://console.cloud.google.com (note its *Project ID*), enable billing + a budget alert, and enable the **BigQuery API**.
2. **Install the Google Cloud CLI**: `brew install --cask google-cloud-sdk`, then open a new Terminal.
3. **Log in:**
   ```bash
   gcloud auth application-default login
   gcloud config set project YOUR_PROJECT_ID
   ```
4. **Configure environment variables** (in the same Terminal, with `.venv` active):
   ```bash
   cp .env.example .env          # edit .env: set GCP_PROJECT_ID
   set -a; source .env; set +a   # loads the variables into this Terminal session
   python scripts/bq_check.py    # must print can_query True + a GB estimate
   ```
5. **Inspect the real GA4 schema** *before* trusting the models:
   ```bash
   python scripts/inspect_ga4_schema.py     # exit code 0 and "MISSING columns: none" = models match the sample
   ```
   If it reports a missing column, or the probe shard `events_20210131` does not exist, fix `src/growthpulse/bigquery.py` / `models/ga4/stg_ga4_events.sql` and the `ga4_*_date` vars in `dbt_project/dbt_project.yml`.
6. **Load the synthetic raw tables** to BigQuery: `python scripts/load_to_bigquery.py`
7. **Run dbt on BigQuery** (from the project folder):
   ```bash
   cd dbt_project
   export DBT_PROFILES_DIR=. DBT_TARGET=bigquery
   dbt debug                       # connection + permissions check
   dbt run                         # builds staging/intermediate/marts + GA4 models
   dbt test                        # data tests (generic + singular)
   dbt docs generate && dbt docs serve   # browse lineage at http://localhost:8080
   cd ..
   ```
   Also pass `--vars '{"data_end_date":"2025-12-28"}'` if you changed the generated date range.
8. **Show BigQuery results in the dashboard:** `python scripts/export_bigquery_marts.py` copies the marts into the local DuckDB and writes `data/processed/ga4_funnel.csv` (the GA4 funnel tab appears). Re-run `python scripts/run_pipeline.py` to return to purely local results (it rebuilds the marts).
9. **Clean up** to stop charges: `bq rm -r -d YOUR_PROJECT_ID:growthpulse_raw` and likewise for `growthpulse_staging`, `_intermediate`, `_marts`, `_ga4` (or delete them in the console).

## Datasets created
`growthpulse_raw` (loaded CSVs), `growthpulse_staging`, `growthpulse_intermediate`, `growthpulse_marts`, `growthpulse_ga4` (prefix = `GP_BQ_DATASET`). All must be in the **US** location to be queried together with the public sample.

## Known limitations of this mode
* Models were not run on BigQuery by the author - expect to debug small issues (types, permissions, dataset locations). Report anything you fix.
* `stg_ga4_events` is the only incremental model (insert_overwrite by `event_date`, 3-day lookback). The sample is static, so incrementality gives no benefit here; it is included to show the production pattern.
* The Python analytics (experiments, MMM, report) run locally on the DuckDB copy of the marts; they are not executed inside BigQuery.
