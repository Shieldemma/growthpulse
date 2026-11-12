# Testing guide

| Layer | What | Command | Typical time |
|---|---|---|---|
| Unit tests | metrics (CAC, ROAS, retention, LTV, zero denominators, NaN), data generator consistency, attribution rules, experiment statistics, MMM transforms / leakage / optimiser, BigQuery config | `python -m pytest -m "not slow"` | ~15 s |
| Integration | full pipeline on a small dataset, SQL-vs-Python attribution parity, join-grain and reconciliation checks, **mutation test** (corrupt data -> dbt tests must fail), report generation | `python -m pytest -m slow` | 1-3 min |
| Dashboard smoke | every page renders without exceptions; filters change numbers; empty selection and missing database give friendly messages; synthetic labels present | included in `-m slow` | |
| dbt tests | 121 generic tests (unique, not_null, accepted_values, relationships, ranges) + 14 singular business-rule tests (the project reports 135 dbt tests passing in the last build) (reconciliation, funnel monotonicity, attribution credit = 1, dates, retention bounds, MMM continuity) | `cd dbt_project && DBT_PROFILES_DIR=. dbt test` | ~15 s |
| Validation | do all expected files/tables/outputs exist (incl. 27 BI tables + CSVs) and do totals reconcile? (102 checks) | `python scripts/validate_project.py` | 2 s |
| BI layer | registry = tables = CSVs, eligible-column logic, ratio-of-sums, freshness table is real, calculated fields use real columns, doc paths exist, Looker link pattern, workflow has no secrets | `tests/test_bi_layer.py` | ~5 s + slow |
| BigQuery offline | compile every model for BigQuery + parse as BigQuery SQL | `python scripts/check_bigquery_sql_offline.py` | ~30 s |

Everything: `python -m pytest` (needs no cloud account). **Not testable without credentials:** anything that actually talks to BigQuery - see `docs/bigquery_setup.md`.

## Reading failures
* `FAILED tests/test_x.py::test_name` - run just that test with `python -m pytest tests/test_x.py::test_name -x -vv`.
* dbt failure - run `dbt test` and read the `Got N results, configured to fail if != 0` line; singular tests print the offending rows when you run the compiled SQL in `dbt_project/target/compiled/`.
* The pipeline stops at the first failing step and records it in `data/processed/pipeline_status.json` (shown on the Data Quality page).
