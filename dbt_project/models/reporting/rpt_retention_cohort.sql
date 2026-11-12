-- BI fact. Grain: cohort_month x acquisition_channel x months_since_start (observable cells only).
-- retention_rate = SUM(customers_retained) / SUM(customers_observed): compute it as a ratio of sums in the BI tool.
select
    cohort_month,
    {{ growthpulse.year_month('cohort_month') }} as cohort_label,
    acquisition_channel as channel_name,
    months_since_start, cohort_size, customers_observed, customers_retained,
    gross_revenue_usd, refunded_usd, net_revenue_usd,
    {{ growthpulse.safe_divide('customers_retained', 'customers_observed') }} as retention_rate
from {{ ref('mart_customer_retention') }}
