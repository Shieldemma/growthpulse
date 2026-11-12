-- Grain: one row per customer x session in the lookback window before signup.
-- This is the journey that attribution models split credit across.
with journey as (
    select
        c.customer_id,
        s.session_id,
        s.session_ts,
        s.channel_name,
        s.campaign_id
    from {{ ref('int_customer_acquisition') }} c
    inner join {{ ref('int_sessions') }} s on s.visitor_id = c.visitor_id
    where s.session_ts <= c.signup_ts
      and {{ growthpulse.days_between('s.session_date', 'c.signup_date') }} <= {{ var('attribution_lookback_days') }}
)
select
    journey.*,
    row_number() over (partition by customer_id order by session_ts, session_id) as touch_number,
    count(*)     over (partition by customer_id)                                 as touch_count
from journey
