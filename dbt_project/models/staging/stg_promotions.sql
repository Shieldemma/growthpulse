-- Grain: one row per promotion window.
select
    cast(promo_id as {{ growthpulse.t_string() }})   as promo_id,
    cast(promo_name as {{ growthpulse.t_string() }}) as promo_name,
    cast(start_date as date)   as start_date,
    cast(end_date as date)     as end_date
from {{ source('growthpulse_raw', 'promotions') }}
