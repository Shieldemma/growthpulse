-- UNVERIFIED on live BigQuery. Grain: one row per transaction_id (unique).
-- GA4 can emit the same purchase more than once, so purchase events are de-duplicated BEFORE any revenue is summed.
select
    transaction_id,
    min(event_ts)   as order_ts,
    min(event_date) as order_date,
    max(user_pseudo_id)   as user_pseudo_id,
    max(ga_session_id)    as ga_session_id,
    max(purchase_revenue_usd) as revenue_usd,
    count(*) as purchase_event_rows
from {{ ref('stg_ga4_events') }}
where event_name = 'purchase' and transaction_id is not null and transaction_id != '(not set)'
group by transaction_id
