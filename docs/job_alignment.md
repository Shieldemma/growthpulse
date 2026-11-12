# Role alignment: Senior Growth / Marketing Data Analyst

This project was built against the responsibilities in a Senior Growth Data Analyst posting from a vacation-rental software company (Barcelona, remote across Europe). The table maps each requirement to the work that demonstrates it. "Built" means implemented and tested in this repo; "Design" means documented but not implemented.

| The role asks for | Status | Evidence |
|---|---|---|
| Analyse paid search, paid social and organic acquisition; explain changes; recommend efficiency gains | Built | Channel and campaign marts, CAC (media and fully loaded), ROAS on mature cohorts, funnel and retention; brand-search cannibalisation flagged in the weekly brief. `dbt_project/models/marts/`, `docs/index.html` §01–02 |
| Run experiments such as geo-tests; state uncertainty and limitations | Built | 3 user-level holdouts (SRM, CIs, power/MDE, CACE) and a 40-region geo test (diff-in-diff, cluster-robust and randomisation p-values, pre-period placebo). `experiment.py`, `geo_lift.py`, tests recover the simulated truth |
| Co-own unified marketing data products with Data Engineering (spend + web + product data) | Built | dbt staging → intermediate → marts → reporting star schema joining ad spend, sessions/events and billing; 44 models, 135 tests; GA4 models for BigQuery. `dbt_project/` |
| Combine attribution with experimental evidence; work on tracking and validation | Built | 4 attribution models in SQL (checked against pandas), compared with experiment results and an MMM calibration table; reconciliation tests between layers. `int_attribution_credit.sql`, `bi_mmm_calibration` |
| Clear narratives and visualisations for marketing stakeholders | Built | Web dashboard with answers first, Looker Studio report, business report labelled FACT / ESTIMATE / RECOMMENDATION. `docs/index.html`, `reports/example/business_report.md` |
| Use AI tools to speed up analysis and automate recurring reports, with accuracy checks | Built (no external AI call) | Deterministic weekly insight brief plus an LLM prompt that may only cite numbers the pipeline computed; scheduled refresh workflow. `insights.py`, `.github/workflows/refresh-bigquery.yml` |
| Document definitions, methods and limitations; build self-service analytics | Built | Data dictionary, Looker Studio field definitions and calculated fields, analytics standards, data-freshness table. `docs/` |
| Data modelling, event streaming (RudderStack) and self-service BI (Omni) | Partly | dbt modelling is built. Event streaming is a design: `docs/tracking_plan.md` (event spec, identity, QA). The `rpt_*` star schema maps directly onto an Omni topic; not implemented in Omni |
| Judgement with noisy data; correlation vs causation | Built | The report overrides the MMM where experiments and economics disagree (display); under-powered tests are reported as inconclusive with the sample size needed |
| CAC / ROAS fluency; trade-offs with stakeholders | Built | Paid vs fully loaded CAC, payback, LTV:CAC hurdle rules, budget scenarios with probability of beating the current mix |
| Nice to have: Marketing Mix Modelling | Built | Adstock, lag, saturation, out-of-time test, bootstrap intervals, diagnostics, budget optimiser, calibration. `src/growthpulse/mmm/` |
| Nice to have: vacation-rental industry | Context | The simulated company sells subscription software to vacation-rental hosts (Starter / Growth / Scale plans) with seasonal promotions |

## Not covered by this project

- Live RudderStack or Omni deployments.
- GEO / AI-search measurement exists as a measurement design only: `docs/geo_ai_search_measurement.md`.
- Cross-functional leadership and mentoring, which code cannot show.
