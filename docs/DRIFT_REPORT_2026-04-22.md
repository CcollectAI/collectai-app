# Router SQL Drift Report

- Schema source: live DB (518 tables/views/matviews, 400 public functions)
- Files scanned: 136
- Total potential drift entries: **44** across 16 files


## `app/agents/deal_desk_router.py` (5)
  - L388 **TABLE_MISSING**: `v_offer_summary_v1`
  - L397 **TABLE_MISSING**: `v_offer_summary_v1`
  - L436 **TABLE_MISSING**: `v_offer_summary_v1`
  - L445 **TABLE_MISSING**: `v_offer_summary_v1`
  - L486 **TABLE_MISSING**: `v_offer_summary_v1`

## `app/agents/deal_risk.py` (1)
  - L38 **COLUMN_MISSING**: `offers.seller_id (used as o.seller_id)`

## `app/agents/intake_feedback_router.py` (2)
  - L110 **TABLE_MISSING**: `scan_corrections`
  - L139 **TABLE_MISSING**: `scan_corrections`

## `app/features/catalog_browser_router.py` (2)
  - L140 **COLUMN_MISSING**: `market_observations.item_ref (used as mo.item_ref)`
  - L140 **COLUMN_MISSING**: `market_observations.item_ref (used as mo.item_ref)`

## `app/features/collections_router.py` (11)
  - L190 **COLUMN_MISSING**: `collections.category (used as c.category)`
  - L190 **COLUMN_MISSING**: `collections.category (used as c.category)`
  - L190 **COLUMN_MISSING**: `collections.collection_key (used as c.collection_key)`
  - L190 **COLUMN_MISSING**: `collections.display_name (used as c.display_name)`
  - L190 **COLUMN_MISSING**: `collections.release_date (used as c.release_date)`
  - L190 **COLUMN_MISSING**: `collections.total_items (used as c.total_items)`
  - L211 **COLUMN_MISSING**: `collections.category (used as c.category)`
  - L211 **COLUMN_MISSING**: `collections.collection_key (used as c.collection_key)`
  - L211 **COLUMN_MISSING**: `collections.display_name (used as c.display_name)`
  - L211 **COLUMN_MISSING**: `collections.release_date (used as c.release_date)`
  - L211 **COLUMN_MISSING**: `collections.total_items (used as c.total_items)`

## `app/features/events/events_announcements.py` (1)
  - L227 **COLUMN_MISSING**: `events.sponsor_company_id (used as e.sponsor_company_id)`

## `app/features/export_router.py` (2)
  - L372 **TABLE_MISSING**: `auth`
  - L384 **TABLE_MISSING**: `columns`

## `app/features/feedback_router.py` (7)
  - L188 **COLUMN_MISSING**: `training_items.corrected_at (used as t.corrected_at)`
  - L188 **COLUMN_MISSING**: `training_items.corrected_at (used as t.corrected_at)`
  - L188 **COLUMN_MISSING**: `training_items.corrected_at (used as t.corrected_at)`
  - L188 **COLUMN_MISSING**: `training_items.corrected_attributes (used as t.corrected_attributes)`
  - L188 **COLUMN_MISSING**: `training_items.corrected_category (used as t.corrected_category)`
  - L188 **COLUMN_MISSING**: `training_items.corrected_price (used as t.corrected_price)`
  - L188 **COLUMN_MISSING**: `training_items.correction_notes (used as t.correction_notes)`

## `app/features/gamification_router.py` (3)
  - L679 **COLUMN_MISSING**: `profiles.avatar_color (used as p.avatar_color)`
  - L679 **COLUMN_MISSING**: `profiles.avatar_url (used as p.avatar_url)`
  - L679 **COLUMN_MISSING**: `profiles.display_name (used as p.display_name)`

## `app/features/items_export_router.py` (1)
  - L52 **TABLE_MISSING**: `columns`

## `app/features/sell_timing_router.py` (1)
  - L62 **TABLE_MISSING**: `created_at`

## `app/features/sponsor_company_router.py` (1)
  - L614 **COLUMN_MISSING**: `events.sponsor_company_id (used as e.sponsor_company_id)`

## `app/features/value_summary_router.py` (1)
  - L143 **TABLE_MISSING**: `deals`

## `app/routes/admin_dashboard.py` (2)
  - L141 **COLUMN_MISSING**: `category_items.user_id (used as ci.user_id)`
  - L141 **TABLE_MISSING**: `auth`

## `app/routes/billing_router.py` (2)
  - L639 **COLUMN_MISSING**: `device_tokens.active (used as dt.active)`
  - L639 **COLUMN_MISSING**: `device_tokens.push_token (used as dt.push_token)`

## `app/routes/user_settings_router.py` (2)
  - L276 **TABLE_MISSING**: `user_alert_preferences`
  - L349 **TABLE_MISSING**: `user_alert_preferences`
