-- Grain: one row per successful payment.
select
    cast(payment_id as {{ growthpulse.t_string() }})           as payment_id,
    cast(subscription_id as {{ growthpulse.t_string() }})      as subscription_id,
    cast(customer_id as {{ growthpulse.t_string() }})          as customer_id,
    cast(payment_date as date)           as payment_date,
    cast(billing_cycle_number as {{ growthpulse.t_int() }})    as billing_cycle_number,
    cast(gross_amount_usd as {{ growthpulse.t_float() }})    as gross_amount_usd,
    cast(currency as {{ growthpulse.t_string() }})             as currency
from {{ source('growthpulse_raw', 'payments') }}
