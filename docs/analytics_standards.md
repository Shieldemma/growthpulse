# Analytics standards (documentation, reporting and visualisation guidelines)

## Metric governance
1. **One definition per metric**, in `docs/methodology.md`; every dashboard links to it. A metric changes only through a pull request that updates the definition, the SQL, the Python function and the tests.
2. **Ratios are ratios of sums** in every tool. Never average a ratio, never show a ratio where the denominator is zero (blank, not 0).
3. **Labelled uncertainty:** model outputs (LTV projection, MMM) show intervals and the label *estimate*; observed values say *observed*; assumptions are listed on the page.
4. **Causal language:** "caused/incremental" only for randomised experiments; attribution and MMM use "associated with / credited to / estimated contribution".
5. **Censoring rule:** ROAS/LTV/retention only use cohorts observed for the full window.
6. **Grain statement** for every table and chart in documentation (`docs/data_dictionary.md`, dbt descriptions).

## Data quality
* dbt tests on every key (unique/not_null), relationships, accepted values, ranges, plus singular tests for reconciliation, funnel monotonicity, attribution credit = 1, retention bounds, MMM continuity, and a test that the BI layer equals the marts.
* A mutation test proves tests fail on corrupted data. `scripts/validate_project.py` for outputs; Looker page 8 shows freshness and test counts.
* Definition of done for a new metric: SQL + Python/DAX/Looker formula + unit test (zero denominator, NaN) + dictionary entry + dashboard note.

## Naming and modelling conventions
`stg_` typed 1:1 views; `int_` business logic; `fct_`/`dim_` facts and dimensions; `mart_` analytical marts; `rpt_` BI-facing flat tables; `bi_` Python-produced result tables. `snake_case`, `_usd` money suffix, `_date`/`_ts`, flags `is_`/`has_` as 0/1, windows `m3/m12`, eligibility columns `*_eligible_*`.

## Visualisation guidelines
* Title = question or takeaway; subtitle = metric definition and window.
* One colour per channel across all pages; red/green only for threshold meaning; colour-blind-safe palette; no 3-D/pie charts for more than 4 slices.
* Start bar axes at zero; show units (USD, %, pp); format rates as %; use reference lines (1.0 ROAS, 3:1 LTV:CAC).
* Show denominators/sample sizes next to rates; grey-out or hide cells under n = 10-30.
* Every page: synthetic-data label, last refresh, filter summary, "how to read" box when the metric is easy to misread (ROAS, attribution, MMM).
* Dashboards answer questions; deep dives live in the report/notebooks.

## Review checklist (before sharing)
Numbers reconcile to the marts (page 8, parity check) · definitions linked · uncertainty shown · filters tested at extremes (single channel, last month) · no sensitive data · credentials mode intentionally chosen · cost controls on.
