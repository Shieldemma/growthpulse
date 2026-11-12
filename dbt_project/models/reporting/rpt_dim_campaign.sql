-- BI dimension. Grain: one row per campaign_id (plus a 'none' row for sessions/customers outside paid campaigns).
select c.campaign_id, c.campaign_name, ch.channel_name, c.objective, c.start_date, c.end_date
from {{ ref('stg_campaigns') }} c
inner join {{ ref('stg_channels') }} ch on ch.channel_id = c.channel_id
union all
select 'none', 'No campaign (organic / owned)', cast(null as {{ growthpulse.t_string() }}),
       cast(null as {{ growthpulse.t_string() }}), cast(null as date), cast(null as date)
