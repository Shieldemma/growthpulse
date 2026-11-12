-- Grain: one row per paid subscription (= one per paying customer).
select
    cast(subscription_id as {{ growthpulse.t_string() }}) as subscription_id,
    cast(customer_id as {{ growthpulse.t_string() }})     as customer_id,
    cast(plan_id as {{ growthpulse.t_string() }})         as plan_id,
    cast(start_date as date)        as start_date,
    cast(cancel_date as date)       as cancel_date,
    cast(end_date as date)          as end_date,
    cast(discount_pct as {{ growthpulse.t_float() }})   as discount_pct,
    cast(discount_cycles as {{ growthpulse.t_int() }})    as discount_cycles
from {{ source('growthpulse_raw', 'subscriptions') }}
