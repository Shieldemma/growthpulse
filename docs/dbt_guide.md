# dbt guide

Project: `dbt_project/` (profile `growthpulse`, connection settings in `dbt_project/profiles.yml`, **env vars only - no secrets**).

```bash
cd dbt_project
export DBT_PROFILES_DIR=.                      # tell dbt where profiles.yml is
export GP_DUCKDB_PATH=../data/processed/growthpulse.duckdb
dbt debug                                      # connection check (local DuckDB)
dbt run  --vars '{"data_end_date":"2025-12-28"}'
dbt test --vars '{"data_end_date":"2025-12-28"}'
dbt build --vars '{"data_end_date":"2025-12-28"}'   # run + test in dependency order
dbt docs generate && dbt docs serve            # lineage graph + column docs at http://localhost:8080
```
BigQuery: `export DBT_TARGET=bigquery GCP_PROJECT_ID=...` then the same commands (see `docs/bigquery_setup.md`).
`data_end_date` marks the last day of data; the pipeline passes the true value from `data/raw/_generation_metadata.json`.

## Folder map
| Path | Purpose |
|---|---|
| `models/staging` | typed 1:1 views over sources (`_sources.yml` declares the raw synthetic tables and the GA4 public sample) |
| `models/intermediate` | business logic: sessions, visitors, acquisition, touchpoints, attribution credit |
| `models/marts` | facts, dimension and 6 marts, each documented with its grain |
| `models/ga4` | BigQuery-only GA4 models (disabled automatically on DuckDB) |
| `macros/portable_sql.sql` | cross-engine helpers: `safe_divide`, `week_start`, `add_months`, `days_between`, type names |
| `macros/generic_tests.sql` | `non_negative`, `expression_is_true`, `between_values` |
| `tests/*.sql` | singular tests (reconciliation, funnel, attribution, dates, retention, MMM) - a test passes when it returns **zero rows** |

## Grain of the important tables
`stg_sessions`: session. `int_visitors`: visitor. `int_customer_acquisition`: customer. `int_touchpoints`: customer x session. `int_attribution_credit`: customer x model x touch. `fct_payments`: payment. `fct_customer_revenue`: paying customer. `fct_marketing_spend`: date x campaign. `mart_marketing_performance`: date x model x channel x campaign (**filter to one model**). `mart_channel_unit_economics`: month x model x channel. `mart_customer_retention`: cohort month x channel x month index. `mart_growth_funnel`: first-visit date x channel x campaign x device. `mart_mmm_weekly`: week.

## Incremental models
Only `stg_ga4_events` (BigQuery) is incremental (`insert_overwrite`, partition by `event_date`, 3-day lookback). Everything else is rebuilt each run because the sources are small and static; making them incremental would add risk without benefit.
