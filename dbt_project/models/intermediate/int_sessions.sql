-- Grain: one row per session. Adds channel names and the visitor's session order.
select
    s.session_id,
    s.visitor_id,
    s.session_ts,
    s.session_date,
    ch.channel_name,
    ch.is_paid,
    s.campaign_id,
    s.device_category,
    row_number() over (partition by s.visitor_id order by s.session_ts, s.session_id) as session_ordinal
from {{ ref('stg_sessions') }} s
inner join {{ ref('stg_channels') }} ch on ch.channel_id = s.channel_id
