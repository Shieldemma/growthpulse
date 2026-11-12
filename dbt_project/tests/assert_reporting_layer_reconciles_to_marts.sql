-- The BI layer must carry exactly the same totals as the marts it is built from (nothing lost or duplicated).
with r as (
    select (select sum(spend_usd) from {{ ref('rpt_marketing_daily') }}) as spend,
           (select sum(new_customers) from {{ ref('rpt_marketing_daily') }}) as customers,
           (select sum(net_revenue_to_date) from {{ ref('rpt_marketing_daily') }}) as revenue,
           (select sum(spend_usd) from {{ ref('rpt_unit_economics_monthly') }}) as ue_spend,
           (select sum(new_customers) from {{ ref('rpt_unit_economics_monthly') }}) as ue_customers,
           (select sum(visitors) from {{ ref('rpt_funnel_daily') }}) as visitors,
           (select count(*) from {{ ref('rpt_customers') }}) as n_customers),
m as (
    select (select sum(spend_usd) from {{ ref('stg_ad_spend') }}) as spend,
           (select count(*) from {{ ref('dim_customers') }} where is_paying = 1) as customers,
           (select sum(net_revenue_usd) from {{ ref('fct_customer_revenue') }}) as revenue,
           (select count(*) from {{ ref('int_visitors') }}) as visitors,
           (select count(*) from {{ ref('dim_customers') }}) as n_customers)
select r.*, m.spend as expected_spend, m.customers as expected_customers
from r, m
where abs(r.spend - m.spend) > 0.01 or abs(r.ue_spend - m.spend) > 0.01
   or abs(r.customers - m.customers) > 0.001 or abs(r.ue_customers - m.customers) > 0.001
   or abs(r.revenue - m.revenue) > 0.01 or r.visitors <> m.visitors or r.n_customers <> m.n_customers
