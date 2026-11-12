-- UNVERIFIED on live BigQuery. Grain: one row per GA4 session (user_pseudo_id x ga_session_id). Events without a
-- ga_session_id cannot be assigned to a session and are excluded (coverage is reported by a dbt test).
select
    concat(user_pseudo_id, '-', cast(ga_session_id as string)) as session_key,
    user_pseudo_id,
    ga_session_id,
    min(event_ts)   as session_start_ts,
    min(event_date) as session_date,
    max(first_user_source)   as first_user_source,
    max(first_user_medium)   as first_user_medium,
    max(first_user_campaign) as first_user_campaign,
    max(device_category)     as device_category,
    max(country)             as country,
    max(case when event_name = 'session_start'  then 1 else 0 end) as has_session_start,
    max(case when event_name = 'view_item'      then 1 else 0 end) as has_view_item,
    max(case when event_name = 'add_to_cart'    then 1 else 0 end) as has_add_to_cart,
    max(case when event_name = 'begin_checkout' then 1 else 0 end) as has_begin_checkout,
    max(case when event_name = 'purchase'       then 1 else 0 end) as has_purchase
from {{ ref('stg_ga4_events') }}
where ga_session_id is not null
group by user_pseudo_id, ga_session_id
