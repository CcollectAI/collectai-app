# Architecture

## System Overview

Sparrow Collect is a collectibles tracking and valuation platform with a React Native mobile app backed by a FastAPI server and Supabase/PostgreSQL database.

```
Mobile App (Expo/React Native)
       │
       ▼
   FastAPI Server (EC2 :8080)
       │
       ├── Supabase / PostgreSQL (data + auth)
       ├── S3 (image storage)
       ├── External APIs (eBay, TCGPlayer, Cardmarket)
       └── Background Workers (price monitor, deal discovery)
```

## Frontend

- **Framework**: Expo SDK 54 + React Native 0.81
- **Routing**: expo-router (file-based)
- **State**: React hooks + AsyncStorage for offline cache
- **API Client**: `src/api/collectorsApi.ts` — typed fetch wrapper
- **Theme**: Tiffany Blue (#81D8D0), dark mode support via `useAppTheme()`
- **Key Libraries**: expo-camera (barcode), expo-haptics, expo-image, FlashList, react-native-reanimated

### Directory Structure

```
app/                    # Screens (file-based routing)
  (tabs)/               # Tab navigator (home, search, scan, events, profile)
  purchase/             # Smart Deal Agent screens
  projects/[id].tsx     # Build & Paint project detail (category-aware)
  build-paint-projects  # Build & Paint project list + create
  categories/           # Category store screens
  analytics.tsx         # Portfolio analytics
  barcode-scan.tsx      # Camera scanner
src/
  api/                  # API client
  components/           # Reusable UI (Skeleton, Toast, LoadingButton, OfflineBanner)
  constants/            # buildStepTemplates.ts, categoryFields.ts
  data/                 # SupabaseDataProvider, types, categories (CATEGORY_VISUAL)
  hooks/                # useFormField, useEnterReveal, useNetworkStatus
  lib/                  # validate.ts, marketProviders/
  theme/                # colors, useAppTheme
types/                  # category.ts (36 categories)
```

## Backend

- **Framework**: FastAPI on Uvicorn
- **Database**: asyncpg direct connections to Supabase PostgreSQL
- **Auth**: JWT (Supabase-issued) + DEV_MODE bypass for local development
- **Workers**: Standalone Python processes for async tasks

### 6 Agentic Layers

| Agent | Purpose | Key File |
|-------|---------|----------|
| Pricing | Ridge regression v2, q10/q50/q90 quantile predictions | `app/ml/model_loader.py` |
| Alert & Insight | Threshold, anomaly, set completion alerts | `app/agents/alert_agent.py` |
| Learning & Calibration | Feedback loop, calibration gate | `app/agents/calibration_agent.py` |
| Vision & Classification | 2-tier: OpenAI Vision → heuristic (54 categories). CLIP/fal.ai tier removed 2026-07-27 — FAL_KEY was never set, so it never ran | `app/ml/vision_classifier.py` |
| Marketplace Aggregation | Multi-source search, dedup, provenance scoring | `app/agents/marketplace_agent.py` |
| Smart Deal | Purchase mandates, policy engine, deal discovery | `app/agents/deal_discovery_agent.py` |
| Catalog Learning | Capture unrecognized items, auto-map by consensus, surface new category candidates | `features/catalog_learning_router.py` |

### Server Directory Structure

```
server/
  main.py               # FastAPI app, lifespan, router registration
  app/
    auth.py              # JWT validation, DEV_MODE, API key guards
    config.py            # Environment config with validation
    db.py                # asyncpg pool management
    db_helpers.py        # User-scoped query wrappers (RLS supplement)
    errors.py            # Standardized error_response()
    models/              # Pydantic response models
    routes/              # API routers (items, portfolio, pipeline, settings, etc.)
    features/            # Feature routers (events, quickscan, taxonomy)
    agents/              # Business logic agents (marketplace, deal, dossier)
    ml/                  # ML model loading, inference, vision
    lib/                 # Utilities (affiliate, s3_client, notify)
  workers/               # Background workers (17 registered)
    watchlist_monitor_worker.py   # Watchlist price monitoring (priority tiers: 15min/1hr/6hr)
    price_monitor_worker.py       # Threshold, anomaly, set completion alerts
    deal_discovery_worker.py      # Purchase mandate scanning + deal alerts
    auction_alert_worker.py       # Auction end-time alerts (5min cycle, eBay/Yahoo/Catawiki)
    value_change_worker.py        # Portfolio value change notifications
    insights_digest_worker.py     # Weekly collection digest
    catalog_learning_worker.py    # Auto-map + candidate pipeline
    vision_ingest_worker.py       # Vision classification queue
    alerts_worker.py              # Low-value item alerts
    event_scraper_scheduler.py    # Event ingestion (6hr cycle: crawl 41 targets + dedup + enrich)
    retry.py                      # Retry + dead letter infrastructure
  pipelines/             # Data ingestion and training pipelines
  tests/                 # pytest test suite (1486+ tests)
```

## Database Schema

Key tables in Supabase PostgreSQL:

| Table | Purpose |
|-------|---------|
| `items` | User collection items |
| `category_items` | Marketplace reference data per category |
| `model_registry` | ML model versions and metrics |
| `market_hits` | Price observations from marketplaces |
| `events` | Collector events (shows, conventions) |
| `event_attendees` | Event RSVPs |
| `user_category_follows` | Category notification preferences |
| `purchase_mandates` | Smart Deal Agent buy orders |
| `mandate_deals` | Matched deals for mandates |
| `user_settings` | Per-user preferences (currency, region, locale) |
| `catalog_suggestions` | User-submitted unrecognized item signals |
| `category_candidates` | Aggregated new category proposals |
| `event_templates` | Reusable event templates (save-as-template / create-from-template) |
| `sponsor_companies` | Sponsor company registrations + Stripe checkout |
| `event_announcements` | One-way broadcast messages from event hosts to attendees |
| `event_announcement_reads` | Read receipts for announcements (auto-mark-read) |
| `build_paint_projects` | Build & paint project tracking (category-specific status pipelines) |
| `build_step_templates` | Category-specific build workflow step templates |
| `notification_history` | Push notification log with read/unread tracking |
| `user_push_tokens` | Expo push notification tokens per device |
| `taxonomy_registry` | Category taxonomy versions |
| `object_pointers` | S3 image references |

### `items` paired columns — read this before adding a writer

`items` deliberately carries **both halves** of three pairs, and different
readers key on different halves:

| Pair | Who reads which half |
|------|----------------------|
| `name` ↔ `title` | Home portfolio and `/portfolio/overview` read `name`; the Items tab falls back to `title` |
| `purchased_at` ↔ `purchase_date` | `ITEMS_SELECT` (`itemsProvider.ts`) reads `purchased_at`; the CSV export reads `purchase_date` |
| `purchase_price` ↔ `purchase_price_eur` | The analytics Cost Basis / DCA series sums the EUR half |

Writing one half and not the other **never throws**. A `SELECT` of the
unwritten half returns NULL and every reader defaults (`?? 0`, `'Untitled'`),
so the feature renders empty instead of failing. That is why this recurred:
the 2026-07-24 fix landed on `add-manual.tsx` and was never carried to
`routes/items_router.py`, `features/import_router.py` or
`pipelines/seed_beta_users.py`. Measured 2026-07-28, before the fix,
`purchase_price_eur` was non-null on **0 of 5** priced rows — the Cost Basis
card could not populate for anyone.

Since 2026-07-28, **`trg_items_sync_paired_columns` (BEFORE INSERT OR UPDATE)
derives the missing half**, so a new writer no longer has to remember. Two
things it deliberately does not do:

- it never overwrites a half that *was* supplied — the watchlist "I Got It!"
  flow sends a real timestamp, not a date, and keeps it
- it will not treat a non-EUR row as EUR; the database cannot call the FX
  service. App-side conversion is `app/lib/fx_service.py::convert_to_eur`,
  wired into all three server writers.

#### `user_settings`: currency / region / locale — code and CHECK must agree

`PUT /settings` writes three constrained columns. Each has a code-side allow-list
that is the intended contract, and each must match its CHECK exactly:

| Column | Code allow-list | Values |
|--------|-----------------|--------|
| `currency` | `CurrencyCode` (`src/data/types.ts`), `VALID_CURRENCIES` | EUR, USD, GBP, JPY, **KRW, AUD, CAD** |
| `region` | `Region` (`src/lib/settings.tsx`), `VALID_REGIONS` | americas, europe, japan, **korea, oceania**, other |
| `locale` | `NumberLocale`, `VALID_LOCALES` | en-US, de-DE, ja-JP, nl-NL, **ko-KR, en-AU** |

Until 2026-07-30 **all three CHECKs were missing the bold values** — Korea and
Oceania support was added throughout the code and the constraints were never
migrated with it. The handler validated the value as legal, the INSERT then
raised 23514, and the user got a generic **500 `DB_ERROR`**.

This was not cosmetic. `REGION_DEFAULTS` maps `korea → KRW` and
`oceania → AUD`, and hands those out as **first-launch defaults**, so a Korean
user could save neither their currency, nor their region, nor their locale —
three 500s on the values the app itself chose for them. `docs/store-description.md`
also promises "seven currencies … you can change them anytime" on the App Store
listing. Proven on prod: the 4 legacy values 200, the 5 new ones 500.

Migrations `20260730_user_settings_currency_seven.sql` and
`20260730_user_settings_region_locale_korea_oceania.sql`. All 7 currencies, 6
regions and 6 locales now return 200; illegal values still 400 with the valid list.

`user_settings.locale` is the **number-format** locale (`NumberLocale`). The UI
language is a different set — `SUPPORTED_LOCALES` in `src/i18n/index.ts`
(`en,nl,de,fr,es,ja,ko`). Don't merge them.

Deliberately still 4: `verified_sales.currency`. Its CHECK and
`feedback_router.ALLOWED_CURRENCIES` **agree**, so there is no silent failure —
and `miscApi.submitVerifiedSale` has zero FE callers. Widen both together if
verified sales are ever wired to the UI.

> **Why `check-constraint-drift.mjs` did not catch this, or the alerts
> `direction: 'below'` bug:** that gate matches a literal only when it can see
> the constrained column near a mention of its **table**. FE code never mentions
> a table — it posts to an endpoint. So every constraint reachable only through
> an API call is invisible to it. Mutation-tested 2026-07-30: reintroducing
> `direction: 'below'` still reports PASS. The FE-side defence is typing those
> payload fields as **literal unions rather than `string`** (see
> `AlertDirection` / `AlertTriggerType` in `src/api/alertsApi.ts`), which `tsc`
> enforces in `verify:prebuild`. A generic scanner was considered and rejected:
> matching on column name alone collides badly (FE `category` means `pokemon`,
> the constrained `category` means `scanning`/`collection`), and 46 of the 46
> candidates it produced were mostly false positives.

#### Money math: always use the EUR half, never the raw one

`price_predictions.q50` — the source of every "current value", "market value"
and portfolio total — is **EUR**. `items.purchase_price` is raw, denominated in
`items.purchase_currency`. Putting the two in one expression silently mixes
units: a USD 100 and a EUR 100 each contribute 100. Nothing errors, and for a
EUR-only user the numbers even look right, which is why three separate queries
carried this defect at once (all fixed 2026-07-28):

| Site | Was | Effect |
|------|-----|--------|
| `portfolio_router.py` `/portfolio/items` | `cost_basis = COALESCE(e.first_q50, 0)` | `unrealized_pl` measured **model drift, not profit** — a stable model reported ~break-even no matter what the user paid. Proved on prod: an item bought for €50 with `first_q50` 8.22 reported `cost_basis` 8.22 and P/L **0.00**; correct values are 50.00 and **−41.78**. |
| `value_summary_router.py` `/value-summary` | `pp.q50 - i.purchase_price` | Smart-buy savings compared EUR against a raw amount, corrupting both the `q50 > purchase_price` filter and the total. |
| `trends_and_deepdive_router.py` DCA series | `SUM(i.purchase_price)` | Cost-basis line plotted in mixed currencies against an EUR value line. (Endpoint is currently dead code — see `app/analytics.tsx:143`.) |

**Rule: if an expression touches `q50`, use `purchase_price_eur`.** Fall back to
`first_q50` only when there is no purchase price on file, so items the user
never priced keep a sensible value instead of dropping to zero.

Two places that correctly use the raw column, so don't "fix" them:
`items_export_router.py` (exports the amount *with* `purchase_currency`) and
`dossier_agent.py` (emits `amount` + `currency` as a pair).

Note this class is **invisible to `scripts/audit_column_drift.py`**, which asks
a structural question — is a column read but never written. Here both columns
had readers and writers; the defect was choosing the wrong one. Structural
audits cannot catch a semantic substitution, so this needs the value-level
check described in the QA checklist.

#### One valuation expression, or the screen contradicts itself

An item's current value is:

```sql
COALESCE(l.q50, i.predicted_price_eur, i.estimated_value, 0)
```

a model prediction if one exists, **else the item's own stored value**. Most
items added by hand have no `price_predictions` row at all, so an endpoint that
uses `COALESCE(l.q50, 0)` alone values them at zero while a sibling endpoint
counts them. The screen then disagrees with itself and there is no error
anywhere.

Measured 2026-07-28 on a live account whose 3 items have **zero**
`price_predictions` rows:

| | `/portfolio/overview` | `/portfolio/items` | `/portfolio/category-stats` |
|---|---|---|---|
| before | 55.00 | rows sum to 0.00 | 0.00 |
| after | 55.00 | 55.00 | 55.00 |

`/portfolio/overview` had already been fixed for this once — its query still
carries the comment "Home's COLLECTION VALUE read €0 vs €55 elsewhere" — and
the fix was never carried to the siblings. **Grep the expression, not the
file.**

Related: never filter `AND category IS NOT NULL` in a breakdown. It silently
drops uncategorised items, so the parts stop adding up to the total the header
shows. Group on `COALESCE(NULLIF(category, ''), 'uncategorized')` instead
(done in `portfolio_router`, `trends_and_deepdive_router`, `insights_router`).

##### There are TWO prediction tables. Use both.

| table | what it is | joined by | historically read by |
|-------|-----------|-----------|----------------------|
| `price_predictions` | catalog-model output, partitioned | `items.canonical_ref = item_ref` | `/portfolio/overview`, `/portfolio/items`, `/portfolio/timeseries` |
| `quick_predictions` | per-item QuickScan output | `item_id = items.id` | `/analytics/portfolio/category-breakdown`, **and the Items tab** (`itemsProvider.mapItemRow`) |

An item priced in one but not the other counted on some Home surfaces and read
**zero** on others. Measured 2026-07-29 across 11 live items: 1 had a quick
prediction, 2 had a catalog one — **neither source dominates**, so picking
either alone loses real value. Every value site must COALESCE over *both*
before falling back to `predicted_price_eur` / `estimated_value`.

##### The Home curve must value the whole collection

`/portfolio/timeseries` drives three of Home's most prominent numbers at once —
the headline **COLLECTION VALUE**, the chart, and the **change %**. It summed
`pp.q50` per day, so a hand-added item contributed 0 to every point while the
Items tab counted it.

The `len(points) < 2` fallback computed the correct total, which meant the bug
**only appeared once an account had ≥2 days of prediction history** — a state
no test account was in. Items without predictions have no history either, so
their value is now a constant baseline added to every day, which keeps the last
point equal to `/portfolio/overview`.

Verified on a deliberately mixed account (one item with 2 days of catalog
predictions at 220, one with a stored value of 120):

| | timeseries | overview | overview rows | category-breakdown | portfolio/items |
|---|---|---|---|---|---|
| before | 220 | 340 | 340 | **120** | 340 |
| after | **340** | 340 | 340 | **340** | 340 |

**Known residual:** the Items tab reads Supabase directly and cannot join
`price_predictions` (no FK for a PostgREST embed — see
`learning_listitems_pgrst_embed`), so a catalog-only-priced item still reads 0
there. Home is internally consistent; closing that last seam needs the Items
tab to read the server, or a denormalised value column on `items`.

#### `chat_threads_v1` user FKs — added 2026-07-31, two different semantics

The table had **no foreign keys to `auth.users`**, so deleting a user left
threads pointing at nobody. Before the fix: of 7 `kind='dm'` threads, 2 had an
orphaned `dm_user_a` and 4 an orphaned `dm_user_b` (5 distinct threads); of 10
threads total, 8 had an orphaned `created_by`.

Never user-visible — `v_chat_inbox_v1` LEFT JOINs `profiles`, so orphans
rendered through the `'Unknown'` fallback. It surfaced because `offers.buyer_id`
**does** have an FK: seeding a test offer against one of those ids failed loudly
with `offers_buyer_id_fkey`. Same class of reference, opposite behaviour.

| Column | On user delete | Why |
|--------|----------------|-----|
| `dm_user_a`, `dm_user_b` | **CASCADE** | A DM is meaningless once either party is gone, and the view already requires both non-null. Messages/members/reads follow via the existing `thread_id` cascades. |
| `created_by` | **SET NULL** | CASCADE would be *wrong*: it would destroy shared `category`/`private` threads whose creator merely left, taking every other member's history. Needed `DROP NOT NULL`, safe because `created_by` has **zero readers** in the codebase — it is write-only. |

Migration `20260731_chat_threads_user_fks.sql`; deleted rows backed up to
`/opt/collectors/logs/chat_orphan_backup_20260731.json`. Proven after applying:
created a user + DM thread + message, deleted the user, and the thread and
message both went to 0 with 0 orphans remaining.

**Not added:** `chat_messages_v1.user_id → auth.users`. Zero orphans today, and
the right semantics are unclear — deleting an author should arguably keep a
group thread readable rather than punch holes in it. Revisit as a
tombstone/anonymise decision, not a bare CASCADE.

#### Empty is not always broken

Two analytics endpoints return empty for a correct reason. Verified by querying
the joins directly rather than inferring from the response — check the same way
before "fixing" either:

- `/portfolio/category-health` → `{"health": []}` needs ≥1 `price_predictions`
  row within 30 days to compute volatility and trend.
- `/sets/auto-progress` → `{"sets": [], ...}` until the user owns **2+ items
  from the same set**. The handler defaults `min_owned=2` with
  `HAVING COUNT(*) >= $2`, so one matching item surfaces nothing. Re-verified
  2026-07-31: seeding a second item with the same `attrs->>'set_name'` returned
  `owned_count 2 / catalog_total 989 / completion_pct 0.2` immediately. **This
  paid feature works — do not cut it on the strength of an empty response.**
  Note the two sides read *different* columns: `items.attrs` but
  `category_items.attributes_json` (see `learning_verify_table_columns_before_sql`).
- `/data-moat/prediction-accuracy` → `total_ground_truths: 0` because
  `price_ground_truths` has never had a row. The write chain **is** fully
  wired: item detail (`useItemDetail.ts:289`) → `submitVerifiedSale` →
  `POST /feedback/verified-sale` → `record_price_ground_truth`. It only fills
  when a user marks an item sold, which no test data does.

The same class, but rendering a *wrong* value rather than none — the leaderboard
showed **XP as money** (fixed 2026-07-31):

- `/gamification/leaderboard` is an **XP** board (`total_xp`, `level`,
  `current_streak`). `app/leaderboard.tsx` poured those into the shape of the
  local `USER_PROFILES` sample, which ranks by collection value —
  `totalEstimatedValueEur: entry.xp` — and the card renders that field through
  `formatPrice`. Against the live board, 80 XP displayed as **"€80.00"**, level
  as "1 item", and every row read "0 categories". `current_streak` was fetched
  and dropped.
- Nothing caught it: 200 response, types satisfied (both numbers), no render
  error. **Only comparing the value to its meaning finds this** — see
  `learning_validate_values_not_just_structure`.
- Fixed by giving each source its own display strings via the exported pure
  `apiEntryToRow`, pinned in `__tests__/screens/leaderboardRow.test.ts` against
  the live board and mutation-proven (5 of 7 assertions fail on the old
  behaviour). Two sources that measure different things must not share a
  view-model.

A third case is a **real** mismatch that was still left unwired on purpose:

- `RegionalInsightsSection` ("Popular in Your Region") is never rendered.
  `marketplace.tsx` reads `resp.items` from
  `GET /data-moat/demand-heat/by-region`, but that endpoint returns
  `{regions: [...]}` — grouped by `region, country_code`, with **no
  `item_key`**. So `items` is always `undefined` and the section self-hides.
  Verified 2026-07-30.

  It was deliberately **not** wired, because the data cannot support it: over 7
  days `demand_signals` held 68 rows of which only **9 had a region**, across 8
  users. A per-item-by-region query returned 4 rows — 3 of them test artifacts
  (`slot freed`, `test query 2/3`) with a **NULL category**, which the component
  would have crashed on (`item.category.replace(...)`, no guard — since fixed).
  Wiring it today would surface junk to users.

  To wire it later: add an `items` array (item_key, category, signal_count,
  region) to that endpoint **alongside** `regions` so nothing else breaks — the
  FE is already written for exactly that shape — and only once real regional
  signal volume exists.

Two binding traps in the same area, both fixed and both worth not repeating:

- **Never bind a bare `datetime.date` to a `timestamptz` column.** asyncpg
  encodes it as midnight in the *host* timezone, so `purchase_date`
  2024-06-01 stored `purchased_at` = 2024-05-31 22:00Z — a day early for
  every UTC reader. Derive it in SQL pinned to UTC instead.
- **Never bind one parameter to both `$N::timestamptz` and `$N::date`.**
  Postgres infers a date/timestamp type for the parameter and asyncpg then
  rejects the ISO *string* a Pydantic model declares (`expected a
  datetime.date or datetime.datetime instance, got 'str'`). This 500'd every
  `POST /items` carrying a `purchased_at` — the whole watchlist conversion —
  silently, because the route caught it as a generic `DB_ERROR`.

## Data Flow

### Item Intake
```
Barcode Scan → Intake Agent → Taxonomy Resolver → Vision Classifier → Pricing Agent → DB
```

**QuickScan client guardrail (`app/quickscan.tsx`):** the standard scan races the
intake call against an 8s client-side cap (reassurance message at ~4s). On
timeout or a low-confidence result the user is handed off to **Add Manually**
(`app/add-manual.tsx`) with the snapped image; on the low-confidence path the
vision-extracted name / category / condition / attributes are passed through as
route params and pre-filled so the user confirms instead of retyping. Photo
uploads use a dedicated 60s `UPLOAD_TIMEOUT_MS` (not the 5s fast-read default).

### Price Monitoring
```
Scheduler → Price Monitor Worker → Marketplace Agent → Price Update → Alert Agent → Push Notification
```

### Deal Discovery
```
Scheduler → Deal Discovery Worker → Marketplace Agent → Policy Engine → Score Deals → Notify User
```

### Notification System
```
Alert Fired (any worker) → app/lib/notify.py
  ├── Check user preference (notification_preferences JSONB)
  ├── Check frequency cap (5/day free, 15/day pro, 30/day premium)
  ├── Send via Expo Push API (all active tokens)
  └── Persist to notification_history
```

All workers route through the shared `notify_user()` helper which handles:
- **Preference-aware routing**: checks user's notification_preferences before sending
- **Frequency capping**: tier-based daily limits to prevent notification fatigue
- **Graceful fallback**: never crashes the worker if push fails

### Event Ingestion Pipeline
```
event_scraper_scheduler.py (every 6 hours, fully automated)
├── Firecrawl crawler (41 web targets: brands, conventions, retailers)
├── Crawl4AI crawler (same 41 targets, JS rendering for dynamic sites)
├── Newsletter scraper (35+ email-to-category mappings, if IMAP configured)
├── Cross-source deduplication (title similarity + date matching)
└── Enrichment (franchise tagging via 13 keyword patterns + Nominatim geocoding)
```

**41 web targets** covering: Pokemon, MTG, Warhammer, LEGO, Funko, Good Smile, K-pop, Taylor Swift, SDCC, NYCC, PAX, Gen Con, MCM, Essen Spiel, Anime Expo, Comiket, AnimeJapan, Sideshow, Hot Toys, Hasbro Pulse, Bandai, Topps, Pokemon Center, TCGPlayer, StockX, Sneaker News, Discogs, Record Store Day, Hodinkee, Watches & Wonders, Disney Parks, Fragrantica, Penworld, Catawiki, Eventbrite (5 search verticals)

### Build & Paint Status Pipelines

Category-specific status pipelines replace the coarse Active/Backlog/Completed system:

| Category | Pipeline |
|----------|----------|
| Warhammer | Wishlist → Purchased → Unassembled → Assembled → Primed → Battle Ready → Parade Ready → Finished |
| Scale Models | Wishlist → Purchased → Unassembled → Assembled → Primed → Painted → Weathered → Decaled → Finished |
| Gunpla | Wishlist → Purchased → On Sprue → Snap Built → Primed → Painted → Decaled → Top Coated → Finished |
| LEGO | Wishlist → Purchased → Sealed → Building → Built → Modified/MOC → Displayed |
| Keycaps | Wishlist → Parts Ordered → Parts Received → Lubing & Modding → Assembled → Tuned → Finished |

Endpoints: `GET /build-paint/status-pipelines` and `GET /build-paint/status-pipelines/{category_id}`

### Catalog Learning
```
Intake Miss (barcode/photo/url/manual) → catalog_suggestions → Worker (30min cycle)
  ├── 3+ users agree on name + existing category → Auto-map to category_items
  ├── Free-text category, 10+ signals → Track in category_candidates (watching)
  └── 25+ unique users in 30 days → Promote to candidate → Admin review
```

## Security

- JWT validation with issuer + audience + expiry checks
- User-scoped database queries via `db_helpers.py`
- SQL injection prevention via identifier whitelists
- Non-root Docker container
- Hostname-based DEV_MODE guard (localhost/127.* only)
