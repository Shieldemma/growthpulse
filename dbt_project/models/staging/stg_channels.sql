-- Grain: one row per channel. Pass-through with types fixed.
select
    cast(channel_id as {{ growthpulse.t_string() }})   as channel_id,
    cast(channel_name as {{ growthpulse.t_string() }}) as channel_name,
    cast(channel_group as {{ growthpulse.t_string() }}) as channel_group,
    cast(is_paid as {{ growthpulse.t_int() }})         as is_paid
from {{ source('growthpulse_raw', 'channels') }}
