-- Revenue reconciliation: fct_payments / fct_customer_revenue must equal raw payments minus raw refunds.
with raw as (
    select (select sum(gross_amount_usd) from {{ ref('stg_payments') }})
         - (select coalesce(sum(refund_amount_usd), 0.0) from {{ ref('stg_refunds') }}) as net_usd
),
f1 as (select sum(net_amount_usd) as net_usd from {{ ref('fct_payments') }}),
f2 as (select sum(net_revenue_usd) as net_usd from {{ ref('fct_customer_revenue') }})
select raw.net_usd as raw_net, f1.net_usd as fct_payments_net, f2.net_usd as fct_customer_net
from raw, f1, f2
where abs(raw.net_usd - f1.net_usd) > 0.01 or abs(raw.net_usd - f2.net_usd) > 0.01
