-- BI fact (FIRST-TOUCH). Grain: acquisition_month x channel_name. CAC (paid media and fully loaded), ROAS and LTV inputs.
-- overhead_allocated_usd = non-media marketing cost allocated pro-rata to the channel's share of that month's PAID spend.
-- Use the *_eligible_* columns for ROAS / LTV / LTV:CAC (fully observed cohorts only). Ratio columns are NULL when undefined.
select
    acquisition_month,
    {{ growthpulse.year_month('acquisition_month') }} as year_month,
    channel_name,
    spend_usd, overhead_allocated_usd, clicks, signups, trials, new_customers,
    net_revenue_m3, net_revenue_m12, net_revenue_to_date,
    is_eligible_m3, is_eligible_m12,
    spend_usd * is_eligible_m3                  as spend_eligible_m3,
    overhead_allocated_usd * is_eligible_m12    as overhead_eligible_m12,
    spend_usd * is_eligible_m12                 as spend_eligible_m12,
    new_customers * is_eligible_m12             as customers_eligible_m12,
    net_revenue_m3 * is_eligible_m3             as revenue_m3_eligible,
    net_revenue_m12 * is_eligible_m12           as revenue_m12_eligible,
    net_revenue_m12 * is_eligible_m12 * {{ var('gross_margin') }} as gross_profit_m12_eligible,
    cpc, cac_paid_media, cac_fully_loaded, roas_m3, roas_m12, revenue_ltv_m12, gross_profit_ltv_m12
from {{ ref('mart_channel_unit_economics') }}
where attribution_model = 'first_touch'
