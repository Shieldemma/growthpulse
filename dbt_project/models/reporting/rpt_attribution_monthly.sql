-- BI fact. Grain: month_start x attribution_model x channel_name. Compare how rules share credit (NOT causal).
-- Always show ONE attribution_model per chart or put it on an axis/series: spend is repeated per model by design.
with flagged as (
    select p.*,
           case when {{ growthpulse.add_months('metric_date', 11) }} <= {{ growthpulse.data_end_date() }} then 1 else 0 end as is_eligible_m12
    from {{ ref('mart_marketing_performance') }} p
)
select
    {{ growthpulse.month_start('metric_date') }} as month_start,
    {{ growthpulse.year_month('metric_date') }}  as year_month,
    attribution_model, channel_name,
    sum(spend_usd) as spend_usd, sum(signups) as signups, sum(new_customers) as new_customers,
    sum(net_revenue_to_date) as net_revenue_to_date,
    sum(net_revenue_m12 * is_eligible_m12) as revenue_m12_eligible,
    sum(spend_usd * is_eligible_m12) as spend_eligible_m12
from flagged
group by {{ growthpulse.month_start('metric_date') }}, {{ growthpulse.year_month('metric_date') }}, attribution_model, channel_name
