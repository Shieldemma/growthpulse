-- Grain: one row per customer x attribution_model x touchpoint (only touches with credit > 0).
-- For every customer and model the credits sum to exactly 1 (tested).
-- Rule-based models only: they describe how credit is SHARED, they do not prove causation.
with t as (select * from {{ ref('int_touchpoints') }})
select * from (
    select customer_id, 'first_touch' as attribution_model, session_id, channel_name, campaign_id, touch_number, touch_count,
           case when touch_number = 1 then 1.0 else 0.0 end as credit
    from t
    union all
    select customer_id, 'last_touch', session_id, channel_name, campaign_id, touch_number, touch_count,
           case when touch_number = touch_count then 1.0 else 0.0 end
    from t
    union all
    select customer_id, 'linear', session_id, channel_name, campaign_id, touch_number, touch_count,
           1.0 / touch_count
    from t
    union all
    -- Position-based (U-shaped): 40% first, 40% last, 20% shared by the middle touches.
    select customer_id, 'position_based', session_id, channel_name, campaign_id, touch_number, touch_count,
           case
               when touch_count = 1 then 1.0
               when touch_count = 2 then 0.5
               when touch_number = 1 or touch_number = touch_count then 0.4
               else 0.2 / (touch_count - 2)
           end
    from t
) credited
where credit > 0
