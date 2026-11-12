{{
    config(
        materialized = 'incremental',
        incremental_strategy = 'insert_overwrite',
        partition_by = {'field': 'event_date', 'data_type': 'date'},
        on_schema_change = 'append_new_columns'
    )
}}
-- UNVERIFIED against a live BigQuery project (see docs/bigquery_setup.md).
-- Grain: one row per GA4 event (the export has no unique event id).
-- Reads only documented GA4 BigQuery-export columns: event_date (STRING YYYYMMDD), event_timestamp (INT64 microseconds),
-- event_name, user_pseudo_id, event_params (repeated key/value), traffic_source (user-level FIRST acquisition source),
-- device.category, geo.country, ecommerce.transaction_id, ecommerce.purchase_revenue_in_usd.
-- Incremental design: the daily shards are insert-overwritten by event_date partition; on incremental runs only the last
-- 3 days are re-read to absorb late-arriving data. The very first run (or --full-refresh) loads the whole var range.
select
    parse_date('%Y%m%d', event_date)                         as event_date,
    timestamp_micros(event_timestamp)                        as event_ts,
    event_name,
    user_pseudo_id,
    (select value.int_value    from unnest(event_params) where key = 'ga_session_id')  as ga_session_id,
    (select value.string_value from unnest(event_params) where key = 'page_location')  as page_location,
    traffic_source.source                                    as first_user_source,
    traffic_source.medium                                    as first_user_medium,
    traffic_source.name                                      as first_user_campaign,
    device.category                                          as device_category,
    geo.country                                              as country,
    ecommerce.transaction_id                                 as transaction_id,
    ecommerce.purchase_revenue_in_usd                        as purchase_revenue_usd
from {{ source('ga4', 'events') }}
where _table_suffix between '{{ var("ga4_start_date") }}' and '{{ var("ga4_end_date") }}'
  and regexp_contains(_table_suffix, r'^[0-9]{8}$')
{% if is_incremental() %}
  and _table_suffix >= format_date('%Y%m%d', date_sub(_dbt_max_partition, interval 3 day))
{% endif %}
