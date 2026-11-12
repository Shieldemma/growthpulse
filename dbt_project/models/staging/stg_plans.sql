-- Grain: one row per plan.
select
    cast(plan_id as {{ growthpulse.t_string() }})            as plan_id,
    cast(plan_name as {{ growthpulse.t_string() }})          as plan_name,
    cast(monthly_price_usd as {{ growthpulse.t_float() }}) as monthly_price_usd
from {{ source('growthpulse_raw', 'plans') }}
