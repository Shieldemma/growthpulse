-- For every attribution model: credited paying customers = paying customers, credited revenue = total net revenue.
with t as (
    select (select count(*) from {{ ref('dim_customers') }} where is_paying = 1) as customers,
           (select sum(net_revenue_usd) from {{ ref('fct_customer_revenue') }}) as revenue
),
m as (
    select attribution_model, sum(new_customers) as customers, sum(net_revenue_to_date) as revenue
    from {{ ref('mart_marketing_performance') }} group by 1
)
select m.attribution_model, m.customers, t.customers as expected_customers, m.revenue, t.revenue as expected_revenue
from m, t
where abs(m.customers - t.customers) > 0.001 or abs(m.revenue - t.revenue) > 0.01
