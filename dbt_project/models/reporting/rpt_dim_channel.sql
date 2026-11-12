-- BI dimension. Grain: one row per channel (unique channel_name).
select channel_name, replace(channel_name, '_', ' ') as channel_label, channel_group, is_paid
from {{ ref('stg_channels') }}
