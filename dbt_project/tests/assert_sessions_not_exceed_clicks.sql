-- Tracked sessions can never exceed ad-platform clicks for the same campaign-day.
select spend_date, campaign_id, clicks, sessions from {{ ref('fct_marketing_spend') }} where sessions > clicks
