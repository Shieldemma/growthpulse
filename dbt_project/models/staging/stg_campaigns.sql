-- Grain: one row per paid campaign.
select
    cast(campaign_id as {{ growthpulse.t_string() }})   as campaign_id,
    cast(channel_id as {{ growthpulse.t_string() }})    as channel_id,
    cast(campaign_name as {{ growthpulse.t_string() }}) as campaign_name,
    cast(objective as {{ growthpulse.t_string() }})     as objective,
    cast(start_date as date)      as start_date,
    cast(end_date as date)        as end_date
from {{ source('growthpulse_raw', 'campaigns') }}
