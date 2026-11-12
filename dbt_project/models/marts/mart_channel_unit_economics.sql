-- Grain: acquisition_month x attribution_model x channel_name.
-- CAC (paid media)   = media spend / new paying customers.
-- CAC (fully loaded) = (media spend + allocated non-media overhead) / new paying customers.
--   Overhead (salaries, tools, agency, creative) is allocated to PAID channels in proportion to their share of the
--   month's media spend. Organic/owned channels receive no allocation, so their CAC is NULL (not a fake 0).
-- ROAS / LTV columns are only filled for months whose cohort has been observed for the full window
-- (is_eligible_*), otherwise young cohorts would look worse simply because they are young.
with perf as (
    select
        {{ growthpulse.month_start('metric_date') }} as acquisition_month,
        attribution_model, channel_name,
        sum(spend_usd) as spend_usd, sum(clicks) as clicks, sum(signups) as signups, sum(trials) as trials,
        sum(new_customers) as new_customers,
        sum(net_revenue_m3) as net_revenue_m3, sum(net_revenue_m12) as net_revenue_m12,
        sum(net_revenue_to_date) as net_revenue_to_date
    from {{ ref('mart_marketing_performance') }}
    group by 1, 2, 3
),
month_spend as (
    select {{ growthpulse.month_start('spend_date') }} as acquisition_month, sum(spend_usd) as total_paid_spend_usd
    from {{ ref('fct_marketing_spend') }} group by 1
),
overhead as (
    select month_start as acquisition_month, sum(cost_usd) as overhead_usd from {{ ref('stg_overhead') }} group by 1
),
joined as (
    select p.*,
           coalesce(o.overhead_usd, 0.0) * coalesce({{ growthpulse.safe_divide('p.spend_usd', 'ms.total_paid_spend_usd') }}, 0.0) as overhead_allocated_usd,
           {{ growthpulse.add_days(growthpulse.add_months('p.acquisition_month', 1), -1) }} as month_end
    from perf p
    left join month_spend ms on ms.acquisition_month = p.acquisition_month
    left join overhead o on o.acquisition_month = p.acquisition_month
)
select
    acquisition_month, attribution_model, channel_name,
    spend_usd, overhead_allocated_usd, clicks, signups, trials, new_customers,
    case when spend_usd > 0 then {{ growthpulse.safe_divide('spend_usd', 'clicks') }} end as cpc,
    case when spend_usd > 0 then {{ growthpulse.safe_divide('spend_usd', 'new_customers') }} end as cac_paid_media,
    case when spend_usd > 0 then {{ growthpulse.safe_divide('spend_usd + overhead_allocated_usd', 'new_customers') }} end as cac_fully_loaded,
    case when {{ growthpulse.add_months('month_end', 2) }}  <= {{ growthpulse.data_end_date() }} then 1 else 0 end as is_eligible_m3,
    case when {{ growthpulse.add_months('month_end', 11) }} <= {{ growthpulse.data_end_date() }} then 1 else 0 end as is_eligible_m12,
    net_revenue_m3, net_revenue_m12, net_revenue_to_date,
    case when spend_usd > 0 and {{ growthpulse.add_months('month_end', 2) }} <= {{ growthpulse.data_end_date() }}
         then {{ growthpulse.safe_divide('net_revenue_m3', 'spend_usd') }} end as roas_m3,
    case when spend_usd > 0 and {{ growthpulse.add_months('month_end', 11) }} <= {{ growthpulse.data_end_date() }}
         then {{ growthpulse.safe_divide('net_revenue_m12', 'spend_usd') }} end as roas_m12,
    case when {{ growthpulse.add_months('month_end', 11) }} <= {{ growthpulse.data_end_date() }}
         then {{ growthpulse.safe_divide('net_revenue_m12', 'new_customers') }} end as revenue_ltv_m12,
    case when {{ growthpulse.add_months('month_end', 11) }} <= {{ growthpulse.data_end_date() }}
         then {{ growthpulse.safe_divide('net_revenue_m12', 'new_customers') }} * {{ var('gross_margin') }} end as gross_profit_ltv_m12
from joined
