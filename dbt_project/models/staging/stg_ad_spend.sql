-- Grain: spend_date x campaign_id.
select
    cast(spend_date as date)     as spend_date,
    cast(campaign_id as {{ growthpulse.t_string() }})  as campaign_id,
    cast(channel_id as {{ growthpulse.t_string() }})   as channel_id,
    cast(spend_usd as {{ growthpulse.t_float() }})   as spend_usd,
    cast(impressions as {{ growthpulse.t_bigint() }})   as impressions,
    cast(clicks as {{ growthpulse.t_bigint() }})        as clicks
from {{ source('growthpulse_raw', 'ad_spend_daily') }}
