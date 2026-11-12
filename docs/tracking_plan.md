# Tracking plan and event-streaming design (design only — NOT implemented)

> The project does **not** use RudderStack or any live event stream. This document shows how the synthetic `sessions` / `events` tables map to a production, privacy-first, server-side tracking design, so you can discuss it credibly without claiming experience you do not have.

## Principles
* **Server-side first**: collect events from your backend/edge (first-party), forward to the warehouse; use client-side only where needed (page/campaign parameters), consent-aware.
* **One identity model**: `anonymous_id` (cookie/device) -> `user_id` (after signup) -> `account_id`; identity merges recorded in an `identifies` table; never use PII as keys.
* **Schema-first**: every event has a contract (name, required properties, types, owner); violating events go to a quarantine table, not silently dropped.
* **UTM + click-id capture** on first landing, stored on the first event and persisted server-side; AI-search referrals tagged by referrer domain (see `geo_ai_search_measurement.md`).

## Event spec (maps to this project)
| Event | Required properties | Warehouse table (production) | Synthetic equivalent here |
|---|---|---|---|
| `page_viewed` | anonymous_id, session_id, url, referrer, utm_*, click_id, device, ts | `events_page` | row in `sessions` (landing) |
| `pricing_viewed` | anonymous_id, session_id, ts | `events_track` | `events.view_pricing` |
| `signup_started` / `signup_completed` | anonymous_id, user_id (completed), plan_intent, ts | `events_track`, `identifies` | `events.signup_start/complete` |
| `trial_started` | user_id, account_id, plan, ts | `events_track` | `events.trial_start` |
| `subscription_started` / `payment_succeeded` / `refund_issued` | account_id, amount_usd, currency, billing_cycle, ts (from billing system, not the browser) | `billing_*` | `subscriptions`, `payments`, `refunds` |
| `lifecycle_email_sent/opened/clicked` | user_id, program_id, variant, ts | `events_track` | represented by `lifecycle_experiment_users` |

## Data-quality tests to put in dbt for a real stream (examples)
`not_null` on ids/timestamps; `accepted_values` on event names and `currency`; **freshness** on `max(received_at)`; **volume anomaly** (daily events within ±3σ of trailing 14 days); duplicate `message_id` count = 0; `sent_at <= received_at + tolerance`; share of events with `utm_source` null by landing page; identity stitching coverage (share of paid orders with a known first touch).

## Privacy
Consent mode respected; IP truncated/dropped; no PII in properties; retention policy per table; access via least-privilege roles; document the lawful basis with your DPO/legal team (this is not legal advice).
