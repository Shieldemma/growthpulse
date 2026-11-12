-- Open with:  python -c "import duckdb; con = duckdb.connect('data/processed/growthpulse.duckdb', read_only=True); print(con.sql(open('sql/analysis_examples.sql').read().split(';')[0]).df())"
-- Or paste any query below into a DuckDB client attached to data/processed/growthpulse.duckdb

-- 1. Paid-media CAC and customers by channel (first-touch attribution)
select channel_name, round(sum(spend_usd)) as spend, round(sum(new_customers)) as customers,
       round(sum(spend_usd) / nullif(sum(new_customers), 0)) as cac
from gp_marts.mart_marketing_performance
where attribution_model = 'first_touch'
group by 1 having sum(spend_usd) > 0 order by cac;

-- 2. 12-month retention by acquisition channel
select acquisition_channel, round(sum(customers_retained) * 1.0 / sum(customers_observed), 3) as retention_m12
from gp_marts.mart_customer_retention where months_since_start = 12 group by 1 order by 2 desc;

-- 3. How much does last-touch move credit vs first-touch? (customers credited)
select channel_name,
       round(max(case when attribution_model = 'first_touch' then credited_paying_customers end)) as first_touch,
       round(max(case when attribution_model = 'last_touch'  then credited_paying_customers end)) as last_touch
from gp_marts.mart_attribution_comparison group by 1 order by 2 desc;

-- 4. Weekly MMM input
select * from gp_marts.mart_mmm_weekly order by week_start limit 10;
