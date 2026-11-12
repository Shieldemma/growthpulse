-- Grain: metric_date x attribution_model x channel_name x campaign_id.
-- ALWAYS filter to ONE attribution_model when summing: spend is repeated on every model's rows so that each
-- model slice is self-contained (the sum across models would count spend 4 times).
-- metric_date means: spend date for spend, signup date for signups, trial start date for trials,
-- first paid date for new_customers and the revenue windows.
with models as (
    select 'first_touch' as attribution_model union all select 'last_touch'
    union all select 'linear' union all select 'position_based'
),
spend as (
    select s.spend_date as metric_date, m.attribution_model, s.channel_name, s.campaign_id,
           s.spend_usd, s.impressions, s.clicks, s.sessions,
           0.0 as signups, 0.0 as trials, 0.0 as new_customers,
           0.0 as net_revenue_m1, 0.0 as net_revenue_m3, 0.0 as net_revenue_m6, 0.0 as net_revenue_m12,
           0.0 as net_revenue_to_date,
           0.0 as eligible_customers_m3, 0.0 as eligible_customers_m12
    from {{ ref('fct_marketing_spend') }} s
    cross join models m
),
signups as (
    select ca.signup_date as metric_date, ac.attribution_model, ac.channel_name,
           coalesce(ac.campaign_id, 'none') as campaign_id,
           sum(ac.credit) as signups
    from {{ ref('int_attribution_credit') }} ac
    inner join {{ ref('int_customer_acquisition') }} ca on ca.customer_id = ac.customer_id
    group by ca.signup_date, ac.attribution_model, ac.channel_name, coalesce(ac.campaign_id, 'none')
),
trials as (
    select ca.trial_start_date as metric_date, ac.attribution_model, ac.channel_name,
           coalesce(ac.campaign_id, 'none') as campaign_id, sum(ac.credit) as trials
    from {{ ref('int_attribution_credit') }} ac
    inner join {{ ref('int_customer_acquisition') }} ca on ca.customer_id = ac.customer_id
    where ca.has_trial = 1
    group by ca.trial_start_date, ac.attribution_model, ac.channel_name, coalesce(ac.campaign_id, 'none')
),
paid as (
    select ca.paid_start_date as metric_date, ac.attribution_model, ac.channel_name,
           coalesce(ac.campaign_id, 'none') as campaign_id,
           sum(ac.credit) as new_customers,
           sum(ac.credit * r.net_revenue_m1)  as net_revenue_m1,
           sum(ac.credit * r.net_revenue_m3)  as net_revenue_m3,
           sum(ac.credit * r.net_revenue_m6)  as net_revenue_m6,
           sum(ac.credit * r.net_revenue_m12) as net_revenue_m12,
           sum(ac.credit * r.net_revenue_usd) as net_revenue_to_date,
           sum(ac.credit * r.is_observed_m3)  as eligible_customers_m3,
           sum(ac.credit * r.is_observed_m12) as eligible_customers_m12
    from {{ ref('int_attribution_credit') }} ac
    inner join {{ ref('int_customer_acquisition') }} ca on ca.customer_id = ac.customer_id
    inner join {{ ref('fct_customer_revenue') }} r on r.customer_id = ac.customer_id
    where ca.is_paying = 1
    group by ca.paid_start_date, ac.attribution_model, ac.channel_name, coalesce(ac.campaign_id, 'none')
),
unioned as (
    select metric_date, attribution_model, channel_name, campaign_id, spend_usd, impressions, clicks, sessions,
           signups, trials, new_customers, net_revenue_m1, net_revenue_m3, net_revenue_m6, net_revenue_m12,
           net_revenue_to_date, eligible_customers_m3, eligible_customers_m12
    from spend
    union all
    select metric_date, attribution_model, channel_name, campaign_id, 0.0, cast(0 as {{ growthpulse.t_bigint() }}), cast(0 as {{ growthpulse.t_bigint() }}), cast(0 as {{ growthpulse.t_bigint() }}),
           signups, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    from signups
    union all
    select metric_date, attribution_model, channel_name, campaign_id, 0.0, cast(0 as {{ growthpulse.t_bigint() }}), cast(0 as {{ growthpulse.t_bigint() }}), cast(0 as {{ growthpulse.t_bigint() }}),
           0.0, trials, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    from trials
    union all
    select metric_date, attribution_model, channel_name, campaign_id, 0.0, cast(0 as {{ growthpulse.t_bigint() }}), cast(0 as {{ growthpulse.t_bigint() }}), cast(0 as {{ growthpulse.t_bigint() }}),
           0.0, 0.0, new_customers, net_revenue_m1, net_revenue_m3, net_revenue_m6, net_revenue_m12,
           net_revenue_to_date, eligible_customers_m3, eligible_customers_m12
    from paid
)
select
    metric_date, attribution_model, channel_name, campaign_id,
    sum(spend_usd) as spend_usd, sum(impressions) as impressions, sum(clicks) as clicks, sum(sessions) as paid_sessions,
    sum(signups) as signups, sum(trials) as trials, sum(new_customers) as new_customers,
    sum(net_revenue_m1) as net_revenue_m1, sum(net_revenue_m3) as net_revenue_m3,
    sum(net_revenue_m6) as net_revenue_m6, sum(net_revenue_m12) as net_revenue_m12,
    sum(net_revenue_to_date) as net_revenue_to_date,
    sum(eligible_customers_m3) as eligible_customers_m3, sum(eligible_customers_m12) as eligible_customers_m12
from unioned
group by metric_date, attribution_model, channel_name, campaign_id
