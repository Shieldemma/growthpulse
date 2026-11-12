-- Spend must not be duplicated or dropped by joins: staging total = fact total = each attribution-model slice of the mart.
with s as (select sum(spend_usd) as v from {{ ref('stg_ad_spend') }}),
f as (select sum(spend_usd) as v from {{ ref('fct_marketing_spend') }}),
m as (select attribution_model, sum(spend_usd) as v from {{ ref('mart_marketing_performance') }} group by 1)
select m.attribution_model, s.v as staging_spend, f.v as fact_spend, m.v as mart_spend
from s, f, m
where abs(s.v - f.v) > 0.01 or abs(s.v - m.v) > 0.01
