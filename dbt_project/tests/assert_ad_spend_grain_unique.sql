-- Grain test: stg_ad_spend must have exactly one row per spend_date x campaign_id.
select spend_date, campaign_id, count(*) as n from {{ ref('stg_ad_spend') }} group by 1, 2 having count(*) > 1
