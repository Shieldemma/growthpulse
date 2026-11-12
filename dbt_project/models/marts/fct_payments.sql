-- Grain: one row per payment (unique payment_id). Refunds are summed per payment BEFORE joining,
-- so a payment with two refunds can never be duplicated (join-grain protection).
-- Net revenue is dated by the ORIGINAL payment date (refunds are netted back to the payment they reverse).
with refunds as (
    select payment_id, sum(refund_amount_usd) as refunded_usd, count(*) as n_refunds
    from {{ ref('stg_refunds') }}
    group by payment_id
)
select
    p.payment_id,
    p.subscription_id,
    p.customer_id,
    p.payment_date,
    p.billing_cycle_number,
    s.plan_id,
    p.gross_amount_usd,
    coalesce(r.refunded_usd, 0.0) as refunded_usd,
    p.gross_amount_usd - coalesce(r.refunded_usd, 0.0) as net_amount_usd,
    coalesce(r.n_refunds, 0) as n_refunds
from {{ ref('stg_payments') }} p
inner join {{ ref('stg_subscriptions') }} s on s.subscription_id = p.subscription_id
left join refunds r on r.payment_id = p.payment_id
