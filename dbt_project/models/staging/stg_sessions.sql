-- Grain: one row per website session.
select
    cast(session_id as {{ growthpulse.t_string() }})      as session_id,
    cast(visitor_id as {{ growthpulse.t_string() }})      as visitor_id,
    cast(session_ts as timestamp)   as session_ts,
    cast(cast(session_ts as timestamp) as date) as session_date,
    cast(channel_id as {{ growthpulse.t_string() }})      as channel_id,
    cast(campaign_id as {{ growthpulse.t_string() }})     as campaign_id,
    cast(device_category as {{ growthpulse.t_string() }}) as device_category
from {{ source('growthpulse_raw', 'sessions') }}
