-- Grain: one row per PAYING customer (unique customer_id).
-- m1/m3/m6/m12 = net revenue from the first 1/3/6/12 billing cycles. A window is "observed" only if the
-- last cycle of the window could already have been billed by the data end date; otherwise comparisons
-- would be biased by right-censoring (young customers have had less time to pay).
select
    p.customer_id,
    p.subscription_id,
    ca.paid_start_date,
    min(p.payment_date) as first_payment_date,
    max(p.payment_date) as last_payment_date,
    count(*) as n_payments,
    sum(p.gross_amount_usd) as gross_revenue_usd,
    sum(p.refunded_usd)     as refunded_usd,
    sum(p.net_amount_usd)   as net_revenue_usd,
    sum(case when p.billing_cycle_number < 1  then p.net_amount_usd else 0.0 end) as net_revenue_m1,
    sum(case when p.billing_cycle_number < 3  then p.net_amount_usd else 0.0 end) as net_revenue_m3,
    sum(case when p.billing_cycle_number < 6  then p.net_amount_usd else 0.0 end) as net_revenue_m6,
    sum(case when p.billing_cycle_number < 12 then p.net_amount_usd else 0.0 end) as net_revenue_m12,
    case when {{ growthpulse.add_months('ca.paid_start_date', 0)  }} <= {{ growthpulse.data_end_date() }} then 1 else 0 end as is_observed_m1,
    case when {{ growthpulse.add_months('ca.paid_start_date', 2)  }} <= {{ growthpulse.data_end_date() }} then 1 else 0 end as is_observed_m3,
    case when {{ growthpulse.add_months('ca.paid_start_date', 5)  }} <= {{ growthpulse.data_end_date() }} then 1 else 0 end as is_observed_m6,
    case when {{ growthpulse.add_months('ca.paid_start_date', 11) }} <= {{ growthpulse.data_end_date() }} then 1 else 0 end as is_observed_m12
from {{ ref('fct_payments') }} p
inner join {{ ref('int_customer_acquisition') }} ca on ca.customer_id = p.customer_id
group by p.customer_id, p.subscription_id, ca.paid_start_date
