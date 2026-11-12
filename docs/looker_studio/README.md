# Looker Studio implementation guide (primary BI layer)

> **Status — read first.** No Looker Studio report was created by the author: that needs your Google account, and Looker Studio has no public API to create or edit report pages. What *is* provided and verified locally: the BigQuery-ready tables (built and tested on DuckDB with identical SQL), their field definitions, calculated-field formulas, a page-by-page report specification, and a script that generates one-click data-source links (`datasource_links.md`, built from Google's documented Linking API; **unverified** until you click them). Menu names below follow Looker Studio's UI as documented at the time of writing and may have moved; trust the intent, not the exact label.
> All data are **SYNTHETIC**. Put a text box "Synthetic data — not real company performance" on every page.

## 0. What you will build
An 8-page report on BigQuery tables produced by dbt (`<dataset>_reporting`) and by the Python analytics (`<dataset>_analytics`).

| # | Page | Main data sources |
|---|---|---|
| 1 | Executive Growth Overview | `rpt_marketing_daily`, `rpt_unit_economics_monthly`, `bi_recommendations`, `bi_data_freshness` |
| 2 | Channel & Campaign Performance | `rpt_marketing_daily`, `rpt_dim_campaign` |
| 3 | Funnel & Retention | `rpt_funnel_daily`, `rpt_retention_cohort` |
| 4 | CAC, LTV & ROAS | `rpt_unit_economics_monthly`, `rpt_marketing_daily`, `bi_channel_economics` |
| 5 | Attribution Comparison | `rpt_attribution_monthly` |
| 6 | Incrementality (user holdouts, geo-lift, lifecycle) | `bi_experiment_results`, `bi_geo_lift_results`, `bi_geo_lift_weekly`, `bi_lifecycle_results`, `bi_lifecycle_value` |
| 7 | MMM & Budget Scenarios (+ calibration) | `bi_mmm_*` tables, `rpt_mmm_weekly` |
| 8 | Data Quality, Freshness & Methodology | `bi_data_freshness`, `bi_mmm_diagnostics` |

Field list for every table: [`field_definitions.md`](field_definitions.md). Calculated fields: [`calculated_fields.md`](calculated_fields.md). Page and chart specs: [`report_spec.md`](report_spec.md).

## 1. Prerequisites
1. BigQuery mode working per `docs/bigquery_setup.md` through `dbt build` (steps 1-7), then `python scripts/publish_analytics_to_bigquery.py`. In BigQuery you should see datasets `growthpulse_reporting` (10 tables) and `growthpulse_analytics` (17 tables). Quick check: `bq ls PROJECT:growthpulse_reporting`.
2. You can open https://lookerstudio.google.com with the same Google account (free; no Looker Studio Pro needed).
3. Cheapest rehearsal path without any cloud: load the CSVs from `dashboard/bi_exports/` (see `docs/local_fallback_bi.md`); every instruction below works with CSV data sources except the BigQuery-specific ones.

## 2. Create the data sources (once, ~20 minutes)
For **each** of the 27 tables (or just the ones for the pages you build first):
1. Looker Studio home -> **Create -> Data source** -> choose the **BigQuery** connector -> authorise.
2. **My Projects** -> your project -> dataset (`growthpulse_reporting` or `growthpulse_analytics`) -> table -> **Connect**.
   Faster: open the matching link in `datasource_links.md` (regenerate with `python scripts/looker_links.py --project YOUR_PROJECT_ID`); it pre-fills these choices.
3. On the data source screen: rename it `GP - <table>`; set **Data credentials** (section 6 below); click **Data freshness** and choose 12 hours (default for BigQuery) or 4 hours while developing.
4. Check field types (the *Looker Studio type* column in `field_definitions.md`): dates must be **Date** (YYYYMMDD), not Text; money fields -> *Currency (USD)*; rates -> *Percent*. Set default aggregation to **Sum** for additive metrics and **None** for text/dimension fields; for `cac_*`, `roas_*`, `*_ltv_*`, `retention_rate`, `rel_lift*`, `p_value` set **None/Auto** (they are row-level ratios; use the calculated fields instead).
5. Add the calculated fields from `calculated_fields.md` **inside the data source** (so every chart can reuse them) -> **Add a field**.
6. Click **Create report** (first source) / later **Add data** in the report editor for the others.

## 3. Report-level setup
* **Theme and layout:** *Theme and layout* -> Layout: Header on top; canvas 1280 x 900; fonts Inter/Roboto; one accent colour per channel, identical on all pages (paid_search blue, paid_social purple, display orange, affiliate teal, organic_search green, email yellow, referral grey, direct dark grey). Use red only for "bad" thresholds.
* **Page template:** header with title + subtitle; left: filter row; top-right text box "Synthetic data — not real company performance"; bottom text box "Last data day / last pipeline run" from `bi_data_freshness` (two scorecards).
* **Controls on every page** (Insert -> Add a control): *Date range control* (default: Last 12 months or custom full period; Looker Studio applies it to charts whose data source has a Date dimension), *Drop-down list* on `channel_name` (multi-select), *Drop-down list* on `campaign_id` (pages 2,3), *Drop-down* on `device_category` (page 3), *Drop-down* single-select on `attribution_model` (page 5 only; default `first_touch`).
* **Cross-data-source filtering:** controls only filter charts from the data source they are bound to. Either (a) enable Looker Studio's cross-data-source filtering for controls whose field names/types match across sources (look under the control's *Setup* tab / report settings; **verify current availability**), or (b) bind a control per page to that page's main data source (recommended for a portfolio: simpler and predictable). All `rpt_*` facts share `channel_name`, so (a) works for channel filtering when available.
* **Report settings** (*File -> Report settings*): default theme, *Enable viewers to export data* off for sensitive data (fine on for synthetic), data freshness inherited from data sources.

## 4. Build pages
Follow [`report_spec.md`](report_spec.md) top to bottom; each chart lists data source, dimension, metrics, sort, filters and the business explanation to put in the chart's description / a text box. Order of work: page 1 (proves the connection) -> 2 -> 4 -> 3 -> 5 -> 6 -> 7 -> 8.

## 5. Presentation checklist (what hiring managers look at)
1. Each page title states the question (e.g. "Which channels acquire customers profitably?"), each chart title states the *takeaway pattern* ("Display costs more per customer than it earns").
2. A "How to read" box on pages 4-7 (ROAS is not profit; attribution is not causal; MMM intervals; experiments are causal for what was tested).
3. Consistent number formats: USD no decimals for spend, 1 decimal for ratios, % for rates; CAC/ROAS tables with conditional colours (ROAS < 1 red, > 3 green).
4. Final check: set the date range to the full period, channel = all; compare 6 numbers with `reports/business_report.md` (total spend, customers, paid-media CAC, ROAS 12m by channel, experiment lifts).

## 6. Data credentials and sharing (summary; full text in `docs/bi_connection_and_refresh.md`)
* **Owner's credentials** (default for a portfolio): viewers need no Google Cloud access, but *every* viewer's interaction runs queries billed to the data-source owner, and anyone with report access sees all data in those tables. Use only with synthetic data in a dedicated, budget-capped project.
* **Viewer's credentials:** each viewer needs BigQuery Data Viewer on the datasets and BigQuery Job User on a billing project; use for private/company data.
* Share: *Share -> Manage access* -> add named people, or *Anyone with the link can view* **only** for synthetic portfolio data. Never share the underlying BigQuery datasets publicly. Use **Schedule email delivery** for PDF snapshots (a cached alternative to live access).

## 7. Verify (after building)
* Page 8 freshness card shows today's pipeline run and `is_synthetic = 1`.
* Compare against the local fallback: a number on page 1 equals the same number in `dashboard/bi_exports/rpt_marketing_daily.csv` (sum `spend_usd`).
* `python scripts/bq_parity_check.py` -> all measures match.
