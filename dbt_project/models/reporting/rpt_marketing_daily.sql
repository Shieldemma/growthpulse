-- BI fact (FIRST-TOUCH attribution only, so spend is never repeated). Grain: metric_date x channel_name x campaign_id.
-- All metrics are SUMS; ratios (CAC, ROAS...) must be computed as SUM(a)/SUM(b) in the BI tool (never average a ratio).
-- *_eligible columns contain the value only for dates whose cohort has been observed for the full window, and 0 otherwise,
-- so SUM(revenue_m12_eligible) / SUM(spend_eligible_m12) is a censoring-safe ROAS.
with base as (
    select * from {{ ref('mart_marketing_performance') }} where attribution_model = 'first_touch'
),
flagged as (
    select base.*,
           case when {{ growthpulse.add_months('metric_date', 2) }}  <= {{ growthpulse.data_end_date() }} then 1 else 0 end as is_eligible_m3,
           case when {{ growthpulse.add_months('metric_date', 11) }} <= {{ growthpulse.data_end_date() }} then 1 else 0 end as is_eligible_m12
    from base
)
select
    metric_date,
    {{ growthpulse.week_start('metric_date') }}  as week_start,
    {{ growthpulse.month_start('metric_date') }} as month_start,
    {{ growthpulse.year_month('metric_date') }}  as year_month,
    attribution_model, channel_name, campaign_id,
    spend_usd, impressions, clicks, paid_sessions, signups, trials, new_customers,
    net_revenue_m3, net_revenue_m12, net_revenue_to_date,
    is_eligible_m3, is_eligible_m12,
    spend_usd * is_eligible_m3        as spend_eligible_m3,
    new_customers * is_eligible_m3    as customers_eligible_m3,
    net_revenue_m3 * is_eligible_m3   as revenue_m3_eligible,
    spend_usd * is_eligible_m12       as spend_eligible_m12,
    new_customers * is_eligible_m12   as customers_eligible_m12,
    net_revenue_m12 * is_eligible_m12 as revenue_m12_eligible,
    net_revenue_m12 * is_eligible_m12 * {{ var('gross_margin') }} as gross_profit_m12_eligible
from flagged
