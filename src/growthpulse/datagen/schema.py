"""Schema of the SYNTHETIC raw tables (single source of truth).

Used by:
  * the DuckDB loader (column types),
  * the BigQuery loader (mapped to BigQuery types),
  * the auto-generated data dictionary (docs/data_dictionary.md).

Each table maps to: grain (what one row means) and a list of
(column, duckdb_type, description) tuples.
All timestamps are UTC. All money is USD. Flags are 0/1 integers.
"""
from __future__ import annotations

TABLES: dict[str, dict] = {
    "channels": {
        "grain": "one row per marketing channel",
        "columns": [
            ("channel_id", "VARCHAR", "Primary key, e.g. ch_paid_search"),
            ("channel_name", "VARCHAR", "Human-readable channel name"),
            ("channel_group", "VARCHAR", "paid | owned | organic"),
            ("is_paid", "INTEGER", "1 if the channel has ad spend"),
        ],
    },
    "campaigns": {
        "grain": "one row per paid campaign",
        "columns": [
            ("campaign_id", "VARCHAR", "Primary key, e.g. ps_brand"),
            ("channel_id", "VARCHAR", "FK -> channels.channel_id"),
            ("campaign_name", "VARCHAR", "Campaign display name"),
            ("objective", "VARCHAR", "Campaign objective"),
            ("start_date", "DATE", "First day campaign could spend"),
            ("end_date", "DATE", "Last day campaign could spend (NULL = still running)"),
        ],
    },
    "ad_spend_daily": {
        "grain": "one row per spend_date x campaign_id",
        "columns": [
            ("spend_date", "DATE", "Calendar day of the spend"),
            ("campaign_id", "VARCHAR", "FK -> campaigns.campaign_id"),
            ("channel_id", "VARCHAR", "FK -> channels.channel_id (denormalised)"),
            ("spend_usd", "DOUBLE", "Media spend in USD"),
            ("impressions", "BIGINT", "Ad impressions"),
            ("clicks", "BIGINT", "Ad clicks"),
        ],
    },
    "marketing_overhead_monthly": {
        "grain": "one row per month x cost_category",
        "columns": [
            ("month_start", "DATE", "First day of month"),
            ("cost_category", "VARCHAR", "team_salaries | tools | agency_fees | creative_production"),
            ("cost_usd", "DOUBLE", "Non-media marketing cost in USD (used for fully loaded CAC)"),
        ],
    },
    "promotions": {
        "grain": "one row per promotion window",
        "columns": [
            ("promo_id", "VARCHAR", "Primary key"),
            ("promo_name", "VARCHAR", "Promotion name"),
            ("start_date", "DATE", "First day (inclusive)"),
            ("end_date", "DATE", "Last day (inclusive)"),
        ],
    },
    "plans": {
        "grain": "one row per subscription plan",
        "columns": [
            ("plan_id", "VARCHAR", "Primary key"),
            ("plan_name", "VARCHAR", "Plan name"),
            ("monthly_price_usd", "DOUBLE", "List price per month in USD"),
        ],
    },
    "sessions": {
        "grain": "one row per website session (pre-signup journey only)",
        "columns": [
            ("session_id", "VARCHAR", "Primary key"),
            ("visitor_id", "VARCHAR", "Anonymous visitor (cookie-like) identifier"),
            ("session_ts", "TIMESTAMP", "Session start (UTC)"),
            ("channel_id", "VARCHAR", "FK -> channels.channel_id (traffic source of the session)"),
            ("campaign_id", "VARCHAR", "FK -> campaigns.campaign_id; NULL for non-paid sessions"),
            ("device_category", "VARCHAR", "desktop | mobile | tablet"),
        ],
    },
    "events": {
        "grain": "one row per funnel event (session_start is implicit in sessions)",
        "columns": [
            ("event_id", "BIGINT", "Primary key"),
            ("session_id", "VARCHAR", "FK -> sessions.session_id"),
            ("visitor_id", "VARCHAR", "FK -> sessions.visitor_id"),
            ("customer_id", "VARCHAR", "Set on signup_complete / trial_start only"),
            ("event_ts", "TIMESTAMP", "Event time (UTC)"),
            ("event_name", "VARCHAR", "view_pricing | signup_start | signup_complete | trial_start"),
        ],
    },
    "customers": {
        "grain": "one row per account created (signup_complete); not all become paying",
        "columns": [
            ("customer_id", "VARCHAR", "Primary key"),
            ("visitor_id", "VARCHAR", "Visitor who signed up"),
            ("signup_ts", "TIMESTAMP", "Account creation (UTC)"),
            ("country", "VARCHAR", "Country code"),
            ("segment", "VARCHAR", "smb | mid_market | enterprise"),
        ],
    },
    "subscriptions": {
        "grain": "one row per paid subscription (one per paying customer)",
        "columns": [
            ("subscription_id", "VARCHAR", "Primary key"),
            ("customer_id", "VARCHAR", "FK -> customers.customer_id"),
            ("plan_id", "VARCHAR", "FK -> plans.plan_id"),
            ("start_date", "DATE", "First paid day (trial conversion date)"),
            ("cancel_date", "DATE", "Date cancellation was requested (NULL if none)"),
            ("end_date", "DATE", "Date access ends = first unpaid renewal (NULL if active)"),
            ("discount_pct", "DOUBLE", "Discount fraction applied to early cycles (0-1)"),
            ("discount_cycles", "INTEGER", "Number of initial billing cycles discounted"),
        ],
    },
    "payments": {
        "grain": "one row per successful monthly payment",
        "columns": [
            ("payment_id", "VARCHAR", "Primary key"),
            ("subscription_id", "VARCHAR", "FK -> subscriptions.subscription_id"),
            ("customer_id", "VARCHAR", "FK -> customers.customer_id"),
            ("payment_date", "DATE", "Payment date"),
            ("billing_cycle_number", "INTEGER", "0 = first payment, 1 = first renewal, ..."),
            ("gross_amount_usd", "DOUBLE", "Amount charged in USD"),
            ("currency", "VARCHAR", "Always USD"),
        ],
    },
    "refunds": {
        "grain": "one row per refund",
        "columns": [
            ("refund_id", "VARCHAR", "Primary key"),
            ("payment_id", "VARCHAR", "FK -> payments.payment_id"),
            ("refund_date", "DATE", "Refund date"),
            ("refund_amount_usd", "DOUBLE", "Amount refunded in USD (<= payment amount)"),
        ],
    },
    "experiment_catalog": {
        "grain": "one row per incrementality experiment",
        "columns": [
            ("experiment_id", "VARCHAR", "Primary key"),
            ("experiment_name", "VARCHAR", "Short name"),
            ("hypothesis", "VARCHAR", "Business hypothesis"),
            ("channel_id", "VARCHAR", "Channel tested"),
            ("start_date", "DATE", "Experiment start"),
            ("end_date", "DATE", "Experiment end"),
            ("outcome_window_days", "INTEGER", "Days after assignment in which conversion counts"),
            ("planned_alpha", "DOUBLE", "Pre-registered significance level"),
            ("test_spend_usd", "DOUBLE", "Media spend during the test"),
            ("attributed_revenue_usd", "DOUBLE", "Revenue a last-touch report credits to the campaign"),
        ],
    },
    "experiment_assignments": {
        "grain": "one row per experimental unit (user) per experiment",
        "columns": [
            ("experiment_id", "VARCHAR", "FK -> experiment_catalog.experiment_id"),
            ("unit_id", "VARCHAR", "Experimental unit (synthetic user)"),
            ("assigned_group", "VARCHAR", "treatment | control"),
            ("assignment_date", "DATE", "Date of random assignment"),
            ("device_category", "VARCHAR", "Pre-treatment covariate"),
            ("prior_sessions", "INTEGER", "Pre-treatment covariate: sessions before assignment"),
            ("was_exposed", "INTEGER", "1 if user actually saw the ads (compliance)"),
            ("converted", "INTEGER", "1 if converted to paid within outcome window"),
            ("revenue_usd", "DOUBLE", "First-payment revenue if converted else 0"),
        ],
    },
    "geo_experiment_catalog": {
        "grain": "one row per geo experiment",
        "columns": [
            ("experiment_id", "VARCHAR", "Primary key"),
            ("experiment_name", "VARCHAR", "Short name"),
            ("hypothesis", "VARCHAR", "Business hypothesis"),
            ("channel_id", "VARCHAR", "Channel tested"),
            ("pre_start_date", "DATE", "First day of the pre-period"),
            ("test_start_date", "DATE", "First day the campaign is ON in treatment geos"),
            ("test_end_date", "DATE", "Last day of the test"),
            ("n_geos", "INTEGER", "Number of geographic units"),
        ],
    },
    "geo_daily_outcomes": {
        "grain": "one row per geo_id x activity_date",
        "columns": [
            ("geo_id", "VARCHAR", "Geographic unit (synthetic market)"),
            ("activity_date", "DATE", "Calendar day"),
            ("assigned_group", "VARCHAR", "treatment | control (assigned once per geo)"),
            ("population_index", "DOUBLE", "Relative market size (mean = 1)"),
            ("spend_usd", "DOUBLE", "Campaign spend in that geo-day (0 pre-period and in control geos)"),
            ("conversions", "INTEGER", "New paid conversions in that geo-day"),
            ("revenue_usd", "DOUBLE", "First-payment revenue in that geo-day"),
        ],
    },
    "lifecycle_experiment_catalog": {
        "grain": "one row per lifecycle (CRM) experiment",
        "columns": [
            ("experiment_id", "VARCHAR", "Primary key"),
            ("experiment_name", "VARCHAR", "Short name"),
            ("hypothesis", "VARCHAR", "Business hypothesis"),
            ("start_date", "DATE", "First assignment date"),
            ("end_date", "DATE", "Last assignment date"),
            ("program_cost_usd", "DOUBLE", "Total program cost for treated users"),
            ("planned_alpha", "DOUBLE", "Pre-registered significance level"),
        ],
    },
    "lifecycle_experiment_users": {
        "grain": "one row per trial user per lifecycle experiment",
        "columns": [
            ("experiment_id", "VARCHAR", "FK -> lifecycle_experiment_catalog.experiment_id"),
            ("unit_id", "VARCHAR", "Experimental unit (synthetic trial user)"),
            ("assigned_group", "VARCHAR", "treatment | control"),
            ("assignment_date", "DATE", "Date of random assignment"),
            ("device_category", "VARCHAR", "Pre-treatment covariate"),
            ("plan_id", "VARCHAR", "Plan chosen if the user pays"),
            ("paid_30d", "INTEGER", "1 if converted to paid within 30 days"),
            ("active_90d", "INTEGER", "1 if still paying at 90 days"),
            ("active_180d", "INTEGER", "1 if still paying at 180 days"),
            ("revenue_30d", "DOUBLE", "Net revenue collected within 30 days"),
            ("revenue_90d", "DOUBLE", "Cumulative revenue within 90 days"),
            ("revenue_180d", "DOUBLE", "Cumulative revenue within 180 days"),
        ],
    },
}

BQ_TYPE_MAP = {
    "VARCHAR": "STRING",
    "INTEGER": "INT64",
    "BIGINT": "INT64",
    "DOUBLE": "FLOAT64",
    "DATE": "DATE",
    "TIMESTAMP": "TIMESTAMP",
}


def columns(table: str) -> list[str]:
    return [c[0] for c in TABLES[table]["columns"]]


def duckdb_types(table: str) -> dict[str, str]:
    return {c[0]: c[1] for c in TABLES[table]["columns"]}
