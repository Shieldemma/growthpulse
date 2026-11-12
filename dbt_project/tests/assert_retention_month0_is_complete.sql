-- Month 0 retention must be exactly 100% (every paying customer paid their first cycle).
select * from {{ ref('mart_customer_retention') }}
where months_since_start = 0 and customers_retained <> customers_observed
