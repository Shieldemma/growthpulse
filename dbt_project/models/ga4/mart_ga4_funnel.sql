-- UNVERIFIED on live BigQuery. Grain: session_date x first_user_medium x device_category.
-- Each step counts SESSIONS in which the event occurred (not strictly sequential: a session can contain a purchase
-- without a tracked view_item). GA4 sample data has no ad cost, so no CAC/ROAS is computed here.
select
    session_date,
    coalesce(first_user_medium, '(none)') as first_user_medium,
    coalesce(device_category, '(unknown)') as device_category,
    count(*) as sessions,
    sum(has_view_item)      as sessions_view_item,
    sum(has_add_to_cart)    as sessions_add_to_cart,
    sum(has_begin_checkout) as sessions_begin_checkout,
    sum(has_purchase)       as sessions_purchase
from {{ ref('int_ga4_sessions') }}
group by 1, 2, 3
