-- Grain: one row per refund.
select
    cast(refund_id as {{ growthpulse.t_string() }})           as refund_id,
    cast(payment_id as {{ growthpulse.t_string() }})          as payment_id,
    cast(refund_date as date)           as refund_date,
    cast(refund_amount_usd as {{ growthpulse.t_float() }})  as refund_amount_usd
from {{ source('growthpulse_raw', 'refunds') }}
