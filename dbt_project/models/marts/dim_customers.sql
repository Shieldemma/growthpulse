-- Grain: one row per customer (account). Descriptive attributes + acquisition + lifecycle status.
select
    ca.customer_id,
    ca.visitor_id,
    ca.signup_date,
    ca.country,
    ca.segment,
    ca.first_channel_name,
    ca.first_campaign_id,
    ca.first_device_category,
    ca.n_sessions,
    ca.has_trial,
    ca.is_paying,
    ca.plan_id,
    ca.paid_start_date,
    {{ growthpulse.month_start('ca.paid_start_date') }} as cohort_month,
    s.cancel_date,
    s.end_date as subscription_end_date,
    case when ca.is_paying = 1 and s.end_date is null then 1 else 0 end as is_active,
    coalesce(r.net_revenue_usd, 0.0) as net_revenue_to_date_usd
from {{ ref('int_customer_acquisition') }} ca
left join {{ ref('stg_subscriptions') }} s on s.subscription_id = ca.subscription_id
left join {{ ref('fct_customer_revenue') }} r on r.customer_id = ca.customer_id
