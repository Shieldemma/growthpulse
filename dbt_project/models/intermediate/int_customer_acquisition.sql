-- Grain: one row per customer (= account created). Joins the signup to first-touch, trial and paid conversion.
with trial as (
    select customer_id, min(event_ts) as trial_start_ts
    from {{ ref('stg_events') }}
    where event_name = 'trial_start' and customer_id is not null
    group by customer_id
)
select
    c.customer_id,
    c.visitor_id,
    c.signup_ts,
    c.signup_date,
    c.country,
    c.segment,
    v.first_session_date,
    v.first_channel_name,
    v.first_campaign_id,
    v.first_device_category,
    v.n_sessions,
    t.trial_start_ts,
    cast(t.trial_start_ts as date) as trial_start_date,
    case when t.customer_id is not null then 1 else 0 end as has_trial,
    s.subscription_id,
    s.plan_id,
    s.start_date as paid_start_date,
    case when s.subscription_id is not null then 1 else 0 end as is_paying,
    {{ growthpulse.days_between('c.signup_date', 's.start_date') }} as days_signup_to_paid
from {{ ref('stg_customers') }} c
inner join {{ ref('int_visitors') }} v on v.visitor_id = c.visitor_id
left join trial t on t.customer_id = c.customer_id
left join {{ ref('stg_subscriptions') }} s on s.customer_id = c.customer_id
