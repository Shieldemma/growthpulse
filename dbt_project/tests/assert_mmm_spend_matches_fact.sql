-- Weekly MMM spend must reconcile to the daily spend fact.
select m.total as mmm_spend, f.total as fact_spend
from (select sum(spend_total) as total from {{ ref('mart_mmm_weekly') }}) m,
     (select sum(spend_usd) as total from {{ ref('fct_marketing_spend') }}) f
where abs(m.total - f.total) > 0.01
