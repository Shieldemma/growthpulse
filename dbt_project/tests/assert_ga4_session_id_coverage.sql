{{ config(enabled = (target.type == 'bigquery'), severity = 'warn') }}
-- UNVERIFIED on live BigQuery. Warn if more than 5% of events lack ga_session_id (they are excluded from session models).
select share_missing from (
    select countif(ga_session_id is null) / count(*) as share_missing from {{ ref('stg_ga4_events') }}
) where share_missing > 0.05
