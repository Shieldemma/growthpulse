select metric_date, channel_name, campaign_id, count(*) as n
from {{ ref('rpt_marketing_daily') }} group by 1, 2, 3 having count(*) > 1
