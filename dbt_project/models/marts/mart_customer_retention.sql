-- Grain: cohort_month x acquisition_channel (first touch) x months_since_start.
-- A customer is "retained at month k" if a payment exists for billing cycle k. A customer only counts at month k
-- if that cycle could already have been billed by the data end date (customers_observed), which avoids
-- right-censoring bias. retention_rate = customers_retained / customers_observed.
with cust as (
    select customer_id, cohort_month, paid_start_date, first_channel_name as acquisition_channel
    from {{ ref('dim_customers') }}
    where is_paying = 1
),
grid as (
    select c.*, m.month_index,
           case when {{ growthpulse.add_months('c.paid_start_date', 'm.month_index') }} <= {{ growthpulse.data_end_date() }}
                then 1 else 0 end as is_observed
    from cust c
    cross join {{ ref('int_month_index') }} m
)
select
    g.cohort_month,
    g.acquisition_channel,
    g.month_index as months_since_start,
    sum(g.is_observed) as customers_observed,
    sum(case when g.is_observed = 1 and p.customer_id is not null then 1 else 0 end) as customers_retained,
    sum(case when g.is_observed = 1 then coalesce(p.gross_amount_usd, 0.0) else 0.0 end) as gross_revenue_usd,
    sum(case when g.is_observed = 1 then coalesce(p.refunded_usd, 0.0) else 0.0 end) as refunded_usd,
    sum(case when g.is_observed = 1 then coalesce(p.net_amount_usd, 0.0) else 0.0 end) as net_revenue_usd,
    count(*) as cohort_size
from grid g
left join {{ ref('fct_payments') }} p
       on p.customer_id = g.customer_id and p.billing_cycle_number = g.month_index
group by g.cohort_month, g.acquisition_channel, g.month_index
having sum(g.is_observed) > 0
