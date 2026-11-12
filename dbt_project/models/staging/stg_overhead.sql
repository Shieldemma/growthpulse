-- Grain: month_start x cost_category (non-media marketing costs used for FULLY LOADED CAC).
select
    cast(month_start as date)      as month_start,
    cast(cost_category as {{ growthpulse.t_string() }})  as cost_category,
    cast(cost_usd as {{ growthpulse.t_float() }})      as cost_usd
from {{ source('growthpulse_raw', 'marketing_overhead_monthly') }}
