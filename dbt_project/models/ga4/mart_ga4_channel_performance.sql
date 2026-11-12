-- UNVERIFIED on live BigQuery. Grain: first_user_source x first_user_medium (user-level FIRST acquisition source, a
-- first-touch view only). Revenue comes from de-duplicated orders joined to sessions on session_key.
with orders as (
    select concat(user_pseudo_id, '-', cast(ga_session_id as string)) as session_key,
           sum(revenue_usd) as revenue_usd, count(*) as orders
    from {{ ref('fct_ga4_orders') }}
    where ga_session_id is not null
    group by 1
)
select
    coalesce(s.first_user_source, '(direct)') as first_user_source,
    coalesce(s.first_user_medium, '(none)')   as first_user_medium,
    count(*) as sessions,
    sum(s.has_purchase) as purchasing_sessions,
    coalesce(sum(o.orders), 0) as orders,
    coalesce(sum(o.revenue_usd), 0.0) as revenue_usd,
    {{ growthpulse.safe_divide('sum(s.has_purchase)', 'count(*)') }} as session_conversion_rate,
    {{ growthpulse.safe_divide('coalesce(sum(o.revenue_usd), 0.0)', 'count(*)') }} as revenue_per_session
from {{ ref('int_ga4_sessions') }} s
left join orders o on o.session_key = s.session_key
group by 1, 2
