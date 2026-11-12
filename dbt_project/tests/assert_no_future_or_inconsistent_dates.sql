-- Payments/refunds/subscriptions must not be dated after the data end, and refunds cannot precede their payment.
select 'payment_after_end' as issue, payment_id as id from {{ ref('stg_payments') }} where payment_date > {{ growthpulse.data_end_date() }}
union all
select 'refund_after_end', refund_id from {{ ref('stg_refunds') }} where refund_date > {{ growthpulse.data_end_date() }}
union all
select 'refund_before_payment', r.refund_id from {{ ref('stg_refunds') }} r
  inner join {{ ref('stg_payments') }} p on p.payment_id = r.payment_id where r.refund_date < p.payment_date
union all
select 'payment_before_subscription', p.payment_id from {{ ref('stg_payments') }} p
  inner join {{ ref('stg_subscriptions') }} s on s.subscription_id = p.subscription_id where p.payment_date < s.start_date
union all
select 'paid_before_signup', customer_id from {{ ref('int_customer_acquisition') }} where is_paying = 1 and paid_start_date < signup_date
