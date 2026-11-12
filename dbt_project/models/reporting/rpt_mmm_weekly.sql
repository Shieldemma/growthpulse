-- BI fact. Grain: one row per week_start. MMM inputs: outcome (new MRR), spend per paid channel, promotion share.
select
    week_start, {{ growthpulse.year_month('week_start') }} as year_month,
    new_mrr_usd, new_customers,
    spend_paid_search, spend_paid_social, spend_display, spend_affiliate, spend_total,
    promo_share, is_complete_week
from {{ ref('mart_mmm_weekly') }}
