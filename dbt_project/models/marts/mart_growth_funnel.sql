-- Grain: first_session_date x channel_name x campaign_id x device_category (first-touch cohorts of visitors).
-- Each step counts visitors who EVER reached it (so steps are monotonic). Recent cohorts are right-censored.
select
    first_session_date,
    first_channel_name as channel_name,
    coalesce(first_campaign_id, 'none') as campaign_id,
    first_device_category as device_category,
    count(*) as visitors,
    sum(reached_pricing)      as pricing_viewers,
    sum(reached_signup_start) as signup_starters,
    sum(signed_up)            as signups,
    sum(started_trial)        as trials,
    sum(became_paying)        as paying_customers
from {{ ref('int_visitors') }}
group by 1, 2, 3, 4
