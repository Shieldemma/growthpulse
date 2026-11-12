-- Grain: geo_id x activity_date.
select
    cast(geo_id as {{ growthpulse.t_string() }})         as geo_id,
    cast(activity_date as date)                          as activity_date,
    cast(assigned_group as {{ growthpulse.t_string() }}) as assigned_group,
    cast(population_index as {{ growthpulse.t_float() }}) as population_index,
    cast(spend_usd as {{ growthpulse.t_float() }})       as spend_usd,
    cast(conversions as {{ growthpulse.t_int() }})       as conversions,
    cast(revenue_usd as {{ growthpulse.t_float() }})     as revenue_usd
from {{ source('growthpulse_raw', 'geo_daily_outcomes') }}
