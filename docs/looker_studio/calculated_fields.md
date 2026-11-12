# Looker Studio calculated fields

Create these in the data source (**Add a field**). Syntax is Looker Studio's: `SUM()`, `CASE WHEN ... THEN ... END`. All ratios are **ratios of sums** and return NULL (blank) when the denominator is zero, matching the Python/SQL metric rules. Field names are `snake_case` exactly as in the tables. **Unverified by the author in a live report** - paste, then check the red/green validity indicator and compare with `reports/business_report.md`.

## `rpt_marketing_daily`
| Calculated field | Formula | Format |
|---|---|---|
| CPC | `CASE WHEN SUM(clicks) > 0 AND SUM(spend_usd) > 0 THEN SUM(spend_usd) / SUM(clicks) END` | USD 2 dp |
| Cost per signup | `CASE WHEN SUM(signups) > 0 AND SUM(spend_usd) > 0 THEN SUM(spend_usd) / SUM(signups) END` | USD |
| Paid-media CAC | `CASE WHEN SUM(new_customers) > 0 AND SUM(spend_usd) > 0 THEN SUM(spend_usd) / SUM(new_customers) END` | USD |
| Trial-to-paid % | `CASE WHEN SUM(trials) > 0 THEN SUM(new_customers) / SUM(trials) END` | % |
| ROAS 3m (observed cohorts) | `CASE WHEN SUM(spend_eligible_m3) > 0 THEN SUM(revenue_m3_eligible) / SUM(spend_eligible_m3) END` | Number 2 dp |
| ROAS 12m (observed cohorts) | `CASE WHEN SUM(spend_eligible_m12) > 0 THEN SUM(revenue_m12_eligible) / SUM(spend_eligible_m12) END` | Number 2 dp |
| CAC (observed 12m cohorts) | `CASE WHEN SUM(customers_eligible_m12) > 0 AND SUM(spend_eligible_m12) > 0 THEN SUM(spend_eligible_m12) / SUM(customers_eligible_m12) END` | USD |
| Revenue per customer 12m | `CASE WHEN SUM(customers_eligible_m12) > 0 THEN SUM(revenue_m12_eligible) / SUM(customers_eligible_m12) END` | USD |
| Gross-profit LTV 12m | `CASE WHEN SUM(customers_eligible_m12) > 0 THEN SUM(gross_profit_m12_eligible) / SUM(customers_eligible_m12) END` | USD |
| LTV:CAC 12m (paid media) | `CASE WHEN SUM(spend_eligible_m12) > 0 AND SUM(revenue_m12_eligible) > 0 THEN (SUM(gross_profit_m12_eligible) / SUM(customers_eligible_m12)) / (SUM(spend_eligible_m12) / SUM(customers_eligible_m12)) END` | Number 1 dp |
| Net revenue to date | `SUM(net_revenue_to_date)` | USD |

*Optional gross-margin parameter:* create a **Parameter** `Gross margin` (Number, default 0.8) and use `SUM(revenue_m12_eligible) * Gross margin / SUM(customers_eligible_m12)` instead of the pre-baked gross profit column.

## `rpt_unit_economics_monthly`
| Calculated field | Formula |
|---|---|
| CAC fully loaded | `CASE WHEN SUM(spend_usd) > 0 AND SUM(new_customers) > 0 THEN (SUM(spend_usd) + SUM(overhead_allocated_usd)) / SUM(new_customers) END` |
| CAC fully loaded (observed 12m cohorts) | `CASE WHEN SUM(spend_eligible_m12) > 0 AND SUM(customers_eligible_m12) > 0 THEN (SUM(spend_eligible_m12) + SUM(overhead_eligible_m12)) / SUM(customers_eligible_m12) END` |
| Overhead share of CAC | `CASE WHEN SUM(spend_usd) > 0 THEN SUM(overhead_allocated_usd) / (SUM(spend_usd) + SUM(overhead_allocated_usd)) END` |
| LTV:CAC 12m (fully loaded) | `CASE WHEN SUM(spend_eligible_m12) > 0 THEN (SUM(gross_profit_m12_eligible) / SUM(customers_eligible_m12)) / ((SUM(spend_eligible_m12) + SUM(overhead_eligible_m12)) / SUM(customers_eligible_m12)) END` |
| ROAS 12m | `CASE WHEN SUM(spend_eligible_m12) > 0 THEN SUM(revenue_m12_eligible) / SUM(spend_eligible_m12) END` |

## `rpt_funnel_daily`
| Calculated field | Formula |
|---|---|
| Visit→pricing % | `CASE WHEN SUM(visitors) > 0 THEN SUM(pricing_viewers) / SUM(visitors) END` |
| Pricing→signup start % | `CASE WHEN SUM(pricing_viewers) > 0 THEN SUM(signup_starters) / SUM(pricing_viewers) END` |
| Signup start→signup % | `CASE WHEN SUM(signup_starters) > 0 THEN SUM(signups) / SUM(signup_starters) END` |
| Signup→trial % | `CASE WHEN SUM(signups) > 0 THEN SUM(trials) / SUM(signups) END` |
| Trial→paid % | `CASE WHEN SUM(trials) > 0 THEN SUM(paying_customers) / SUM(trials) END` |
| Visit→paid % | `CASE WHEN SUM(visitors) > 0 THEN SUM(paying_customers) / SUM(visitors) END` |

## `rpt_retention_cohort`
| Calculated field | Formula |
|---|---|
| Retention % | `CASE WHEN SUM(customers_observed) > 0 THEN SUM(customers_retained) / SUM(customers_observed) END` |
| Churn % | `CASE WHEN SUM(customers_observed) > 0 THEN 1 - SUM(customers_retained) / SUM(customers_observed) END` |
| Net revenue per observed customer | `CASE WHEN SUM(customers_observed) > 0 THEN SUM(net_revenue_usd) / SUM(customers_observed) END` |

## `rpt_attribution_monthly`
| Calculated field | Formula |
|---|---|
| Credited CAC | `CASE WHEN SUM(new_customers) > 0 AND SUM(spend_usd) > 0 THEN SUM(spend_usd) / SUM(new_customers) END` |
| ROAS 12m (credited) | `CASE WHEN SUM(spend_eligible_m12) > 0 THEN SUM(revenue_m12_eligible) / SUM(spend_eligible_m12) END` |
Use the chart option **Show data as: percent of total** on `new_customers` to display each channel's share of credit.

## Result tables (`bi_*`)
These are already row-level results (one row per experiment / channel / scenario): add them as-is with aggregation **None** (or MAX). Useful extra fields:
| Table | Calculated field | Formula |
|---|---|---|
| `bi_experiment_results` | Lift label | `CONCAT(ROUND(rel_lift*100,1), "% (", ROUND(rel_lift_ci_low*100,1), "% to ", ROUND(rel_lift_ci_high*100,1), "%)")` |
| `bi_experiment_results` | Attribution overstatement | `attributed_roas - incremental_roas` |
| `bi_mmm_scenarios` | Delta label | `CONCAT("$", ROUND(delta_vs_current,0), " (", ROUND(delta_p05,0), " to ", ROUND(delta_p95,0), ")")` |
| `bi_mmm_channel_summary` | Share label | `CONCAT(ROUND(share_of_revenue*100,1), "% (", ROUND(share_p05*100,1), "% to ", ROUND(share_p95*100,1), "%)")` |
