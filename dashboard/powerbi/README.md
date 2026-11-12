# Power BI version (secondary BI deliverable)

> **No `.pbix` file exists.** Power BI Desktop is a Windows application (Microsoft documents no macOS build) and this project was built on a Mac, so nothing here was opened in Power BI. What is provided: the data model, the measures (`measures.dax`), page layouts, and connection/refresh instructions. The **data** behind it (the same tables as Looker Studio) is built and tested. Treat DAX as a spec to validate against `reports/business_report.md` and the local CSVs.

## 0. Running Power BI from a MacBook Air
| Option | Notes |
|---|---|
| **Windows PC / laptop** | simplest; install Power BI Desktop from the Microsoft Store |
| **Windows virtual machine on the Mac** (Parallels, UTM/QEMU) | Apple-silicon Macs need Windows 11 ARM; Power BI Desktop's ARM support should be confirmed on Microsoft's site; allocate ≥ 8 GB RAM, which a MacBook Air may struggle with |
| **Cloud Windows** (Windows 365 Cloud PC / Azure Virtual Desktop) | works from a browser on macOS; paid |
| **Power BI Service in the browser** (app.powerbi.com) | can author reports from an existing semantic model/dataset with limited features; you still need the model created somewhere (Desktop) or via supported sources like uploaded files |
Because of this, **Looker Studio is the primary deliverable**; use Power BI when a Windows machine is available.

## 1. Data to load
Cloud: BigQuery datasets `<ds>_reporting` and `<ds>_analytics`. Local fallback: the CSVs in `dashboard/bi_exports/` (same names/columns). Load these tables:
`rpt_marketing_daily, rpt_unit_economics_monthly, rpt_funnel_daily, rpt_retention_cohort, rpt_attribution_monthly, rpt_mmm_weekly, rpt_customers` (facts), `rpt_dim_date -> dim_date, rpt_dim_channel -> dim_channel, rpt_dim_campaign -> dim_campaign` (dimensions), and the `bi_*` result tables (no relationships needed).

## 2. Star schema
```
                dim_date (date_day) ──┬── rpt_marketing_daily (metric_date)
                                      ├── rpt_funnel_daily (first_session_date)  [inactive; USERELATIONSHIP if needed]
                                      ├── rpt_unit_economics_monthly (acquisition_month)  [inactive or relate to month_start]
                                      └── rpt_mmm_weekly (week_start)             [inactive; weekly grain]
 dim_channel (channel_name) ──┬── rpt_marketing_daily ─ rpt_unit_economics_monthly ─ rpt_funnel_daily
                              ├── rpt_retention_cohort (channel_name)  └── rpt_attribution_monthly
 dim_campaign (campaign_id) ──── rpt_marketing_daily, rpt_funnel_daily
```
* All relationships: many-to-one from fact to dimension, **single** direction, one active relationship per date role.
* **Mark `dim_date` as the date table** (Table tools -> Mark as date table -> `date_day`).
* `rpt_attribution_monthly`: add a slicer on `attribution_model` (single select, default `first_touch`) or use it as a legend — summing across models multiplies spend by four.
* Hide technical columns (`is_eligible_*`, `*_eligible_*`) from report view and expose the measures instead; set summarisation of ratio columns to "Don't summarize".

## 3. Measures
Copy [`measures.dax`](measures.dax) into a `_Measures` table (Home -> Enter data -> empty table, then New measure). They use the censoring-safe `*_eligible_*` columns, ratio-of-sums, and `DIVIDE` (blank on zero denominator).

## 4. Page layouts (1280 x 720)
| Page | Layout | Visuals |
|---|---|---|
| **Executive Overview** | KPI cards row (Spend, New Customers, Paid-Media CAC, ROAS 12m, LTV to CAC 12m, Net Revenue); left: combo chart Spend (columns) + New Customers (line) by month; right: line CAC vs CAC Fully Loaded by month; bottom: bar LTV to CAC by channel with constant line at 3; table `bi_recommendations`; slicers: Date (between), channel | consistent colours per channel via a theme JSON |
| **Marketing Performance** | matrix (channel > campaign) with Spend, Clicks, CPC, Customers, CAC, ROAS 12m, conditional icons; scatter spend vs ROAS (size = customers); stacked area customers by channel; decomposition tree on New Customers | |
| **Funnel & Retention** | funnel visual using the six step counts; step-rate matrix by channel (conditional formatting); retention heat-map matrix (rows cohort_label, columns months_since_start, values Retention %); line retention by channel | |
| **CAC, LTV, ROAS** | CAC trend lines, overhead share bar, ROAS 3m vs 12m clustered bars, table `bi_channel_economics` | |
| **Attribution** | clustered bars of Credited Customers by channel x model; matrix of Credited CAC; 100% stacked bar Credit Share % | |
| **Incrementality** | tables from `bi_experiment_results`, `bi_geo_lift_results`, `bi_lifecycle_*`; clustered bar Attributed vs Incremental ROAS; line geo indexed series | |
| **MMM & Budget** | line actual vs fitted; stacked area contributions; table channel summary with error bars (use *Analytics pane* where supported) or conditional formatting; line response curves with p05/p95; scenario table + 100% stacked bar of scenario spend; calibration table | |
| **Data Quality** | cards from `bi_data_freshness`; diagnostics table | |
Add a "Synthetic data" text box on every page and tooltips with metric definitions.

## 5. Connect to BigQuery and choose a mode
Home -> Get data -> **Google BigQuery** -> sign in with your Google account -> choose the billing project -> select tables -> **Load** and pick the mode.
| Mode | Behaviour (Microsoft docs: the connector supports both) | Use here? |
|---|---|---|
| **Import** | copies data into the model; fast visuals; data is as old as the last refresh; BigQuery is queried only at refresh | **Recommended** (tables are small) |
| **DirectQuery** | every interaction sends queries to BigQuery; always current but slower, DAX/feature limits, query cost on each use | only if near-real-time matters |
| Composite | mix (large fact DirectQuery + small dims Import) | unnecessary here |
Offline alternative: Get data -> Text/CSV or Folder on `dashboard/bi_exports`.

## 6. Refresh guide (Power BI Service)
1. Publish from Desktop (Home -> Publish) to a workspace.
2. Workspace -> semantic model -> **Settings -> Data source credentials** -> sign in to Google BigQuery.
3. **Scheduled refresh** (Import mode): choose frequency/time; BigQuery is a cloud source, so an on-premises data gateway is **not required** (it is optional; reports from Microsoft forum answers say cloud sources do not need one). Check licence limits on refreshes per day (Pro/Premium differ).
4. Order your refreshes: dbt build / publish script **first**, Power BI refresh **after** (schedule the Power BI refresh a safe interval later than the pipeline), otherwise it will import yesterday's data.
5. **Failures:** expired credentials -> re-enter; timeouts on large tables -> import fewer/smaller tables, reduce columns, retry; schema change -> refresh the query in Power Query (*Refresh preview*), fix renamed columns in M steps.
6. **Caching:** Import = snapshot; DirectQuery visuals use query caches in the service that can be a few hours old — use *Refresh* on the report page.
7. **Costs:** Import refresh scans the selected tables once per refresh; keep a BigQuery budget alert (see `docs/bi_connection_and_refresh.md`).

## 7. Validate
After building: with all channels and the full date range, compare Spend, New Customers, Paid-Media CAC and ROAS 12m per channel with `reports/business_report.md` §1.1 and with `rpt_marketing_daily.csv` (sum `spend_usd`). A mismatch usually means an attribution-model slicer is missing or ratios were averaged.
