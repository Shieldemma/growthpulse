-- Grain: one row per account created (signup). Not every customer pays.
select
    cast(customer_id as {{ growthpulse.t_string() }})   as customer_id,
    cast(visitor_id as {{ growthpulse.t_string() }})    as visitor_id,
    cast(signup_ts as timestamp)  as signup_ts,
    cast(cast(signup_ts as timestamp) as date) as signup_date,
    cast(country as {{ growthpulse.t_string() }})       as country,
    cast(segment as {{ growthpulse.t_string() }})       as segment
from {{ source('growthpulse_raw', 'customers') }}
