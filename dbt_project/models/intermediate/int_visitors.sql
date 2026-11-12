-- Grain: one row per visitor. First-touch attributes + how far the visitor ever progressed in the funnel.
-- Funnel flags are "ever reached" (visitor-level), so they are monotonic by construction.
with first_sessions as (
    select visitor_id, session_ts as first_session_ts, session_date as first_session_date,
           channel_name as first_channel_name, campaign_id as first_campaign_id,
           device_category as first_device_category
    from {{ ref('int_sessions') }}
    where session_ordinal = 1
),
session_counts as (
    select visitor_id, count(*) as n_sessions from {{ ref('int_sessions') }} group by visitor_id
),
event_flags as (
    select
        visitor_id,
        max(case when event_name = 'view_pricing'    then 1 else 0 end) as reached_pricing,
        max(case when event_name = 'signup_start'    then 1 else 0 end) as reached_signup_start,
        max(case when event_name = 'signup_complete' then 1 else 0 end) as signed_up,
        max(case when event_name = 'trial_start'     then 1 else 0 end) as started_trial
    from {{ ref('stg_events') }}
    group by visitor_id
),
paying as (
    select c.visitor_id, 1 as became_paying
    from {{ ref('stg_customers') }} c
    inner join {{ ref('stg_subscriptions') }} s on s.customer_id = c.customer_id
    group by c.visitor_id
)
select
    f.*,
    sc.n_sessions,
    coalesce(e.reached_pricing, 0)      as reached_pricing,
    coalesce(e.reached_signup_start, 0) as reached_signup_start,
    coalesce(e.signed_up, 0)            as signed_up,
    coalesce(e.started_trial, 0)        as started_trial,
    coalesce(p.became_paying, 0)        as became_paying
from first_sessions f
inner join session_counts sc on sc.visitor_id = f.visitor_id
left join event_flags e on e.visitor_id = f.visitor_id
left join paying p on p.visitor_id = f.visitor_id
