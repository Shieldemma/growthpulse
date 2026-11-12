-- BI fact. Grain: first_session_date x channel_name x campaign_id x device_category. Steps = visitors who EVER reached them.
select
    first_session_date,
    {{ growthpulse.month_start('first_session_date') }} as month_start,
    {{ growthpulse.year_month('first_session_date') }}  as year_month,
    channel_name, campaign_id, device_category,
    visitors, pricing_viewers, signup_starters, signups, trials, paying_customers
from {{ ref('mart_growth_funnel') }}
