-- BI dimension/fact for drill-through. Grain: one row per customer (synthetic IDs, no personal data).
select
    customer_id, signup_date, paid_start_date, cohort_month, country, segment,
    first_channel_name as acquisition_channel, coalesce(first_campaign_id, 'none') as acquisition_campaign,
    first_device_category as device_category, plan_id, has_trial, is_paying, is_active, net_revenue_to_date_usd
from {{ ref('dim_customers') }}
