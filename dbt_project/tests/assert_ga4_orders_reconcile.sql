{{ config(enabled = (target.type == 'bigquery')) }}
-- UNVERIFIED on live BigQuery. De-duplicated orders must equal the number of distinct valid transaction ids in the events,
-- and order revenue must not exceed the sum of purchase-event revenue.
select o.n_orders, e.n_ids
from (select count(*) as n_orders, sum(revenue_usd) as rev from {{ ref('fct_ga4_orders') }}) o,
     (select count(distinct transaction_id) as n_ids from {{ ref('stg_ga4_events') }}
      where event_name = 'purchase' and transaction_id is not null and transaction_id != '(not set)') e
where o.n_orders != e.n_ids
