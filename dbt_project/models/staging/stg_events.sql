-- Grain: one row per funnel event (session_start is implicit in stg_sessions).
select
    cast(event_id as {{ growthpulse.t_bigint() }})       as event_id,
    cast(session_id as {{ growthpulse.t_string() }})    as session_id,
    cast(visitor_id as {{ growthpulse.t_string() }})    as visitor_id,
    cast(customer_id as {{ growthpulse.t_string() }})   as customer_id,
    cast(event_ts as timestamp)   as event_ts,
    cast(event_name as {{ growthpulse.t_string() }})    as event_name
from {{ source('growthpulse_raw', 'events') }}
