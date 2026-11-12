-- Grain: spend_date x campaign_id (unique). Spend/impressions/clicks from the ad platforms plus tracked sessions
-- (sessions are counted in a pre-aggregated CTE so the join cannot multiply spend rows).
with sessions as (
    select session_date, campaign_id, count(*) as sessions
    from {{ ref('int_sessions') }}
    where campaign_id is not null
    group by session_date, campaign_id
)
select
    a.spend_date,
    a.campaign_id,
    c.campaign_name,
    ch.channel_name,
    a.spend_usd,
    a.impressions,
    a.clicks,
    coalesce(s.sessions, 0) as sessions
from {{ ref('stg_ad_spend') }} a
inner join {{ ref('stg_campaigns') }} c on c.campaign_id = a.campaign_id
inner join {{ ref('stg_channels') }} ch on ch.channel_id = a.channel_id
left join sessions s on s.session_date = a.spend_date and s.campaign_id = a.campaign_id
