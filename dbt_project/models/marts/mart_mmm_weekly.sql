-- Grain: one row per Monday-based week (unique week_start). Input table for the Marketing Mix Model.
-- Outcome new_mrr_usd = first-payment amount (after discounts, before refunds) of subscriptions that started that week.
-- Spend columns come from the same fct_marketing_spend used everywhere else (reconciled by a dbt test).
-- Only EXOGENOUS controls are included (promotions); sessions/signups are mediators and are deliberately excluded.
with spend as (
    select
        {{ growthpulse.week_start('spend_date') }} as week_start,
        sum(case when channel_name = 'paid_search' then spend_usd else 0.0 end) as spend_paid_search,
        sum(case when channel_name = 'paid_social' then spend_usd else 0.0 end) as spend_paid_social,
        sum(case when channel_name = 'display'     then spend_usd else 0.0 end) as spend_display,
        sum(case when channel_name = 'affiliate'   then spend_usd else 0.0 end) as spend_affiliate,
        sum(spend_usd) as spend_total
    from {{ ref('fct_marketing_spend') }}
    group by 1
),
new_subs as (
    select {{ growthpulse.week_start('payment_date') }} as week_start,
           sum(gross_amount_usd) as new_mrr_usd, count(*) as new_customers
    from {{ ref('fct_payments') }}
    where billing_cycle_number = 0
    group by 1
),
offsets as (
    select 0 as i union all select 1 union all select 2 union all select 3
    union all select 4 union all select 5 union all select 6
),
week_days as (
    select s.week_start, {{ growthpulse.add_days('s.week_start', 'o.i') }} as day_date
    from spend s cross join offsets o
),
promo as (
    select w.week_start, count(*) as promo_days
    from week_days w
    inner join {{ ref('stg_promotions') }} p on w.day_date between p.start_date and p.end_date
    group by w.week_start
)
select
    s.week_start,
    coalesce(n.new_mrr_usd, 0.0) as new_mrr_usd,
    coalesce(n.new_customers, 0) as new_customers,
    s.spend_paid_search, s.spend_paid_social, s.spend_display, s.spend_affiliate, s.spend_total,
    coalesce(p.promo_days, 0) * 1.0 / 7 as promo_share,
    case when {{ growthpulse.add_days('s.week_start', 6) }} <= {{ growthpulse.data_end_date() }} then 1 else 0 end as is_complete_week
from spend s
left join new_subs n on n.week_start = s.week_start
left join promo p on p.week_start = s.week_start
