-- Grain: attribution_model x channel_name. How each rule-based model shares credit for signups, paying customers and
-- revenue-to-date. Differences show how SENSITIVE conclusions are to the rule - not which channel caused sales.
select
    ac.attribution_model,
    ac.channel_name,
    sum(ac.credit) as credited_signups,
    sum(ac.credit * ca.is_paying) as credited_paying_customers,
    sum(ac.credit * coalesce(r.net_revenue_usd, 0.0)) as credited_net_revenue_usd
from {{ ref('int_attribution_credit') }} ac
inner join {{ ref('int_customer_acquisition') }} ca on ca.customer_id = ac.customer_id
left join {{ ref('fct_customer_revenue') }} r on r.customer_id = ac.customer_id
group by ac.attribution_model, ac.channel_name
