# Portfolio write-up - GrowthPulse

## Problem
Leadership of a (fictional, simulated) subscription SaaS company needs to know which marketing channels acquire customers efficiently, what customers are worth, where prospects drop out, whether campaigns cause conversions or merely take credit for them, and how to split the budget - and wants the answers computed reproducibly, tested, and presented with honest uncertainty.

## Approach
1. **Simulated the business** (`src/growthpulse/datagen`): 156 weeks of spend with diminishing returns, multi-session journeys, 14-day trials, churn that is worst early and varies by channel, refunds, discounts, seasonality, promotions, a halo from awareness channels and brand-search cannibalisation. Assumptions are in one file; same seed gives byte-identical files.
2. **Built an analytics-engineering layer** (`dbt_project`): 14 sources -> staging -> intermediate (visitors, customers, touchpoints, attribution credit) -> facts/dimension/marts, with 102 dbt tests (uniqueness, relationships, accepted values, ranges, and singular business-rule tests for reconciliation, funnel monotonicity, attribution credit = 1, retention bounds, MMM continuity). The SAME SQL targets DuckDB (free local) and BigQuery via portable macros.
3. **Defined metrics carefully** (`metrics.py`, `mart_channel_unit_economics`): paid vs fully loaded CAC, observed vs projected LTV, ROAS with right-censoring protection, retention, payback; zero denominators give NaN/NULL.
4. **Compared attribution rules** (first, last, linear, position-based) and stated plainly that they are credit-sharing, not causation.
5. **Measured incrementality** with randomised holdouts (ITT, Newcombe/Katz CIs, SRM, balance, contamination, CACE, power/MDE) on experiments with known truth - so the analysis itself could be tested.
6. **Fitted an MMM** the careful way: simple OLS baseline first, then adstock + lag + saturation + sign constraints, chronological holdout, time-series CV, block bootstrap, sensitivity and diagnostics, budget optimisation under constraints.
7. **Delivered** a static web dashboard (`docs/index.html`, GitHub Pages), a Looker Studio report, an optional 10-page Streamlit explorer, a generated report whose recommendations come from explicit rules over calculated numbers, and Power BI exports/specs.

## Results (SYNTHETIC; numbers from the shipped seed-42 run)
* Lifetime economics span a wide range: paid search ~4:1 projected gross-profit LTV to fully loaded CAC (about 6-month payback) versus display ~0.5:1.
* Display shows an attributed ROAS above 1 but zero measurable incremental lift in its holdout (95% CI roughly -11% to +11%); paid social shows a real +21% lift but a first-payment incremental ROAS of about 0.2.
* Last-touch moves credit to email/direct/referral and away from paid search by roughly a third relative to first-touch - so channel rankings depend on the rule.
* The MMM recovers a 2-week lag for search and beats the raw-spend OLS on held-out weeks (RMSE about 1,521 vs 1,743 USD), but only modestly; several channel intervals include zero, and residuals are autocorrelated - reported as warnings, not hidden.
* Its budget optimiser suggests shifting money to search, but the report overrides the suggested display increase because experiments and unit economics contradict it.

## What I learned / design decisions worth discussing
* Censoring: comparing ROAS across cohorts without windowing by observability is a common silent error - I caught and fixed a real bug of this kind (spend and customers were windowed on different rows) during development; the fix is covered by a unit test.
* Tests must be able to fail: a mutation test corrupts a copy of the data and asserts that dbt's tests catch it.
* Honest modelling beats impressive modelling: the MMM decision rule (>=2% better held-out RMSE) and the "conflict" rule in the report prevent overconfident advice.
* Simulation enables validation: because truth is known, experiment CIs can be checked against it.

## Limitations
Synthetic data only; simplified journeys (paid media is an entry touch only); no involuntary churn, upgrades or annual plans; ~150 weekly MMM observations; MMM uncertainty excludes assumption uncertainty; BigQuery/GA4 mode and the Power BI specs are unverified.

## Skills demonstrated and the files that prove them
| Skill | Evidence |
|---|---|
| Data simulation with known ground truth | `src/growthpulse/datagen/generator.py`, `experiments.py`, `tests/test_datagen.py` |
| SQL (windows, CTEs, grain control, reconciliation) | `dbt_project/models/**`, `dbt_project/tests/*.sql` |
| dbt (sources, staging/intermediate/marts, macros, tests, docs, incremental) | `dbt_project/`, `docs/dbt_guide.md`, `docs/data_dictionary.md` |
| Cross-warehouse portability (DuckDB + BigQuery) | `dbt_project/macros/portable_sql.sql`, `scripts/check_bigquery_sql_offline.py` |
| Python packaging & pipelines | `src/growthpulse/pipeline.py`, `warehouse.py`, `pyproject.toml` |
| Growth metrics (CAC, LTV, ROAS, retention, payback) | `src/growthpulse/metrics.py`, `mart_channel_unit_economics.sql`, `tests/test_metrics.py` |
| Attribution | `int_attribution_credit.sql`, `src/growthpulse/attribution.py`, `tests/test_attribution.py`, `tests/test_pipeline_integration.py` |
| Experimentation & causal inference | `src/growthpulse/experiment.py`, `tests/test_experiment.py` |
| Marketing mix modelling | `src/growthpulse/mmm/*`, `tests/test_mmm.py` |
| Statistical diagnostics & uncertainty | `mmm/model.py` (bootstrap, sensitivity, diagnostics) |
| Leakage prevention | `mmm/data.py::FeatureBuilder`, `test_no_future_leakage_into_training_features` |
| Dashboarding / data-viz (Streamlit, Plotly) | `app/` |
| BI tooling (Power BI modelling, DAX specs) | `dashboard/powerbi/README.md` (unverified), `exports.py` |
| Automated testing strategy | `tests/`, `docs/testing_guide.md` |
| Data quality & observability | `validation.py`, `app/views/p09_quality.py` |
| Business communication & recommendation logic | `reporting.py`, `reports/example/business_report.md` |
| Cloud & credential hygiene | `bigquery.py`, `docs/bigquery_setup.md`, `.env.example`, `.gitignore` |
| Documentation | `README.md`, `docs/` |
