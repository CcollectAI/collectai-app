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

##### The same `, 0` in an AVG, and why SUM was fine (2026-08-10)

`/portfolio/category-stats` closed its fallback chain with `, 0)`:

```sql
AVG(COALESCE(l.q50, <quick_prediction>, i.predicted_price_eur, i.estimated_value, 0))
```

`SUM` and `MAX` already ignore NULLs, so the `0` changed nothing for them. In
`AVG` it is a **sample in the denominator**: every item we cannot price counted
as EUR 0.00. For the 40+ categories with no sold-comp source (watches, whiskey,
lego, warhammer — ~62,000 rows at 0% priced, see the crosswalk table in
CLAUDE.md) the reported average collapsed toward zero. Proven on prod: a user's
`lego` row returned `avg_value 0.00` across 2 items, 0 of them priced.

Now the chain ends at `i.estimated_value` and **NULL means "we do not know"**.
`avg_value` is gone; the endpoint returns `median_value` + `min_item_value` /
`max_item_value` / `priced_count`. A mean is the wrong statistic for a dispersed
category anyway — a EUR 40 Seiko beside a EUR 18,000 Daytona has no meaningful
average. A category with nothing priced returns **null, not 0.0**, and the client
renders "not yet priced".

The value is computed once in a `valued` CTE instead of being copy-pasted into
five aggregates.

> **Why no gate caught it.** `check-silent-failures.mjs` names this exact class
> (`unknown-as-zero`) and scans JS/TS. This was SQL inside a Python string.
> Each new AXIS needs its own sweep.

> **Client compatibility.** Removing `avg_value` breaks any shipped build that
> reads it. `formatPrice` renders `—` for null so it degrades rather than
> crashes, but iOS build 125 shows "avg —" until a build carrying the FE half
> ships. Deploy order matters for response-shape changes.

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
| `quick_predictions` | ~~per-item QuickScan output~~ **catalogue valuation, see below** | `item_id = items.id` | `/analytics/portfolio/category-breakdown`, **and the Items tab** (`itemsProvider.mapItemRow`) |

An item priced in one but not the other counted on some Home surfaces and read
**zero** on others. Measured 2026-07-29 across 11 live items: 1 had a quick
prediction, 2 had a catalog one — **neither source dominates**, so picking
either alone loses real value. Every value site must COALESCE over *both*
before falling back to `predicted_price_eur` / `estimated_value`.

###### CORRECTION 2026-08-19 — the column names lie, and this table did too

`quick_predictions` is **not** QuickScan output. It has exactly ONE writer in
the codebase — `write_quick_valuation` (`items_router.py`), which reads
`price_prediction_daily.q50` and stamps `raw.source = 'catalog_daily'`. It is
**comp-backed**, and calling it "the scan's number" understates it.

`items.predicted_price_eur` sounds like model output. Its only writer was
`app/add-manual.tsx` — the **"Estimated value" text field**. So link 3 of the
chain held a hand-typed guess, one rank ABOVE `estimated_value` where every
other writer puts one. Two member-supplied columns at different ranks meant a
later correction could be outranked by the original and never show.

**Normalised 2026-08-19: `estimated_value` is THE user-estimate column.**
`add-manual` writes it, `updateItem` writes it (it had accepted `price` and
mapped it to nothing — a trap for the offline queue, which replays queued args
verbatim), and QuickScan drafts write it too. `predicted_price_eur` is legacy:
still read, no longer written.

So the four links are two comp/model-backed and two member-supplied:

| link | column / table | backed by |
|---|---|---|
| 1 | `quick_predictions.q50_eur` | the daily catalogue rollup |
| 2 | `price_predictions.q50` via `canonical_ref` | the catalogue model |
| 3 | `items.predicted_price_eur` | **a member typed it** (legacy writes only) |
| 4 | `items.estimated_value` | **a member or a scan** — `attrs.value_entry` says which |

##### `value_source` — the app must say which of those answered

`v_item_values_v1` returns `value_source` alongside `value_eur` (migration
`20260819_v_item_values_v1_value_source.sql`, applied to prod). Same CASE the
COALESCE already walks, so no storage and no backfill:

```
catalog_daily | quick_scan | catalog_model   -> comp/model-backed
user_estimate | app_estimate                 -> nobody checked it
none                                         -> nothing answered; value is 0
```

Before this, a EUR 185 backed by twelve sold comps and a EUR 185 someone typed
were the same pixels. That is hardest to see exactly where it matters most: in
the 40+ categories with **no sold-comp source**, the displayed value IS the
member's own guess wearing the app's authority.

- **FE:** `ValueSourceChip` renders it on item detail and the items list.
  Unknown source renders **nothing** — guessing a provenance is worse than
  showing none. `MARKET_SOURCES` there must match the server's list.
- **The leaderboard ranks on the market-backed subset only** (2026-08-19). It
  is the one number that ranks members in public, so it stops after link 2 —
  otherwise anyone tops a category by typing a bigger number into their own
  item. An item with no comps contributes 0, and in the 40+ uncomped categories
  that is every item, so those are ranked by `metric=items`.
  `server/tests/test_leaderboard_value_parity.py` pins the relationship
  (market-backed → equal; estimate-backed → 0) and is verified against live
  prod from EC2, not from a laptop — the direct DSN does not resolve there
  (`[Errno 8] nodename nor servname` is the tell).
- **`app/item/[id].tsx` no longer derives its own value** — it reads the view
  via `fetchItemValueById`, which reuses `fetchItemValues`. It had been the
  third chain (`predicted_price_eur ?? estimated_value`, skipping both
  prediction tables), and once manual adds stopped writing
  `predicted_price_eur` a new item would have shown a value in the list and
  nothing on its own screen.

**Who consumes `value_source`, and the rule each one follows:**

| surface | rule |
|---|---|
| item detail, items list | `ValueSourceChip` — labels it; unknown claims nothing |
| **leaderboard** | ranks on the market-backed subset ONLY |
| **analytics** | splits into THREE numbers: paid / market / estimated |
| **Home headline** | includes the estimate and **says how much** of the total it is |

`/portfolio/items` returns it per item (2026-08-19), the same way it already
returned `has_purchase_price` — a flag saying which side of the COALESCE
answered. ⚠️ Its CASE mirrors **that query's** order (catalog first, then
quick), NOT the view's (quick first): the label has to name the link that
actually answered there, and the two orders diverge (see above).

##### The three numbers, and why they are not one number

Decided 2026-08-19. What you **paid** is a fact about your past; what the
**market** says is a claim we can back with comps; an **estimate** is an
opinion — the member's own, or a vision scan's. Collapsing the first two is how
`unrealized_pl` came to measure model drift instead of profit; presenting the
third as the second is what `value_source` exists to stop.

`splitPortfolioByValueSource` (`src/lib/portfolioAnalytics.ts`) is the single
implementation. Two rules inside it are judgment calls worth keeping:

- **An unknown `value_source` counts as an ESTIMATE, not as market.** Older
  server builds send none, and defaulting the other way makes the app assert
  comps it does not have.
- **Only a real purchase price sums into "you paid".** Without
  `has_purchase_price` the server falls back to the earliest prediction as cost
  basis, so summing it reports money the member never spent.

The estimated portion is **included and marked, never hidden**: for the 40+
categories with no sold-comp source it is all a member has, and dropping it
would show a collection worth less than they know it is.

> **Capped-aggregate guard on Home.** The headline caption is computed from the
> items Home loaded, and Home loads a PAGE of 50. A money figure summed from a
> page reports a partial number as the whole truth (`verify:silent`'s
> `capped-aggregate`), so the caption renders **only** when fewer rows came back
> than were requested — which proves the whole collection is in hand. At exactly
> 50 it says nothing.

##### A member may override the model, and it has to actually win

Manual add already replaced the member's number silently: it saves what they
typed, then `revalueItem` writes a catalogue valuation into `quick_predictions`
— the TOP of the chain — so a catalogue-linked item started showing our figure
while theirs sat unseen in `estimated_value`.

The item screen now ASKS (`MarketCompPrompt`, added 2026-08-19), after the save
and never as a modal over it. `shouldOfferComp` gates the question on all four
of: the shown value is comp-backed, the member typed something, they have not
already answered, and the two numbers differ **in cents** (`Math.abs(50.01 -
50) >= 0.01` is FALSE in floating point — money is compared as integer cents).

**The answer is honoured by the view**, migration
`20260819b_v_item_values_v1_member_choice.sql`: `attrs.value_choice = 'mine'`
sits ABOVE the model in the COALESCE, and reports as `user_estimate`. Without
that branch the question would be dishonest — both prediction tables outrank
`estimated_value`, and the catalogue model cannot be deleted out of the way
because it is global data, not the member's row.

Proven on prod before and after: with no member having chosen, the value and
source distribution was **byte-identical** (38 user_estimate / 2 catalog_model
/ 2 none), and a probe row flipped 74.80 `catalog_model` → 12.34
`user_estimate` and back. The lock was regenerated and diffed: column list
unchanged, 0 tables differing from a fresh live regen.

Recording 'market' changes no value — it only stops the app asking again, which
is the difference between a question and nagging. And it cannot inflate
anything public: the leaderboard ranks on market-backed sources only, and a
chosen number reports as `user_estimate`.

##### The leaderboard's second axis, for categories value cannot rank

40+ categories have no sold-comp source, and the board sums market-backed value
only — so a value ranking there sorts a column of zeros. Those categories rank
by **unit count** and by **documented share**: items carrying a photo, a
condition AND a purchase price. All three, so the bar is unambiguous, and
because it is the one metric that pays the platform back — count rewards adding
rows, documented share rewards adding the photos and purchase prices the
catalogue and the comp gap are starved of.

`value_ranking_available` is MEASURED off the board rather than a hardcoded
category list, so a category that gains a price source starts offering the value
board by itself. The value chip is hidden, not disabled, where it cannot work.

> ⚠️ **A sort direction cannot be tested on a uniform board.** The first
> version ranked backwards — `ORDER BY documented_pct, documented_count DESC`
> applies DESC to the LAST column only — and every live member being at 0% hid
> it completely. Each metric now carries its own directions and the template
> appends none; `TestLeaderboardOrderDirections` pins that.

##### CATALOGUE-FIRST — one order, everywhere (2026-08-19)

The two comp-backed sources are **not** interchangeable, and the difference is
freshness, not trust:

| source | what it is |
|---|---|
| `price_predictions.q50` | the catalogue model's **current** output, recomputed as sales arrive |
| `quick_predictions.q50_eur` | a **copy** of that price, frozen into the row by `write_quick_valuation` when the item was added or revalued |

The view preferred the frozen copy; `/portfolio/items` preferred the live one.
So an item added in July kept quoting July's price on some screens while the app
labelled it "Market estimate".

**This section previously called that "latent, not live — only 2 items have both
and they agree". That was measured in July and had gone stale.** Re-measured
2026-08-19: 74 active items, 4 with a snapshot, 11 with a live price, **3 with
both — and 2 of them disagreed**, the live price being newer in both cases.

Everything now orders **member choice → live catalogue → frozen snapshot →
`predicted_price_eur` → `estimated_value`**: `v_item_values_v1` (migration
`20260819c`), `/portfolio/items`, `/portfolio/overview`,
`/analytics/portfolio/category-breakdown` and the leaderboard's market-only
subset. `test_leaderboard_value_parity.py` holds the router to it.

Proven the way a value change has to be: every item's value captured before and
after the migration and diffed — **exactly 2 of 76 moved**, both to the live
catalogue figure (34.4291 → 34.4981, 0.0500 → 0.0400), and nothing else
changed. Confirmed through the API afterwards: `Rocket's Scyther` serves 34.5
`catalog_model`.

##### `pct_of_portfolio` is a FRACTION — the seam that got it wrong (2026-08-19)

`/analytics/portfolio/category-breakdown` returns
`pct_of_portfolio = round(val / total_value, 4)`, i.e. **0–1**, and
`test_trends_and_deepdive_router.py` pins `== 0.625` for a category worth 62.5%.
Home's loader assigned it straight into `percentage`, which
`CategoryBreakdownSection` renders BOTH as `percentage.toFixed(0)}%` and as a
bar `width: ${percentage}%`.

Measured on prod, the account with the most items:

| category | value | share | drew | bar |
|---|---|---|---|---|
| pokemon | €79.80 | 51.6% | **"1%"** | 2% (the floor) |
| one_piece_tcg | €74.80 | 48.4% | **"0%"** | 2% (the floor) |

So the chart read as flat and empty while every number behind it was right —
the value chain below had just been proven correct end to end, and the display
of it was wrong by a factor of 100.

**Both sides were self-consistent and both were tested.** The server has a test
pinning the fraction; the component renders whatever it is handed. Only the
JOIN was wrong, which is why nothing caught it
(`learning_verify_the_display_seam_not_isolated_units`). The mapper is now
`src/lib/categoryBreakdown.ts` — extracted from the loader specifically so the
seam has a test — pinned by `__tests__/screens/categoryBreakdownMapper.test.ts`
with the real prod numbers, and proven to fail without the ×100.

**If you add another consumer of this endpoint, multiply.** The unit is not
stated in the field name, which is the whole reason this happened.

##### Stage 2 — CLOSED 2026-08-19: `public.item_value_v1(items)`

The chain lived in five places, made to agree by tests. Agreement held by tests
is not one definition, and this chain had already drifted twice (the missing
catalogue link, the snapshot-vs-live order).

"Have the routers read the view" is impossible — the view ends
`WHERE user_id = auth.uid()` and the server pool has no auth context, which is
why the chain was copied in the first place. A **function** has no such scoping,
so both sides call it:

```
v_item_values_v1              -> LEFT JOIN LATERAL public.item_value_v1(i)
/portfolio/items              -> same
/portfolio/overview (×2)      -> same
/analytics/.../category-breakdown -> same
leaderboard                   -> same, + the market rule as a FILTER on its label
```

The leaderboard is the nicest consequence: it no longer keeps a truncated copy
of the chain, it counts `iv.value_eur` only when `iv.value_source` is
comp-backed. The catalogue step that went missing on 2026-08-17 cannot go
missing again, because it is not written there at all.

**Two traps, both load-bearing:**

- **`SECURITY DEFINER` is not decoration.** `price_predictions` grants SELECT to
  `authenticated` and denies every row by RLS. The view could read it only
  because a view runs with its OWNER's rights; a `SECURITY INVOKER` function
  would re-check as the caller and **succeed while returning nothing**, so every
  catalogue-priced item would silently fall back to the member's estimate.
  Proven as the `authenticated` role after the change: a direct read of
  `price_predictions` returns **0 rows**, the view returns **7 rows, 3
  `catalog_model`**.
- **Call it with `LATERAL`, never `(f(i)).value_eur`.** Postgres expands the
  field-access form into one call PER FIELD, doubling every subquery inside.

**A regression this caught, worth repeating:** the `LEFT JOIN LATERAL` was first
placed between `ON i.user_id = p.user_id` and its `AND i.category = $1`, which
re-parented the category filter onto the lateral's `ON TRUE`. Because a LEFT
JOIN keeps the row when its condition fails, the filter **stopped filtering
instead of erroring** — `item_count` went 1 → 8 and a member appeared on a board
they hold nothing in. Found by diffing each endpoint's JSON against its
pre-refactor capture, which is the only check that would have seen it.

**Proof of no behaviour change:** all four endpoints byte-identical before and
after; the value E2E 12/12; the reminder E2E 10/10; the parity test PASS across
74 items and 7 members; `schema.lock` regen 0 lines; 66 server tests green.
**Cost:** `/portfolio/items` median **54ms** over 8 warm calls, against 55-60ms
before — unchanged. (An early 3-call sample read 120-190ms; that was cold cache
right after the restart, and measuring properly is what stopped a
non-existent regression being "fixed".)

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

**~~Known residual~~ — CLOSED 2026-08-11 by `public.v_item_values_v1`.**

The residual was real and larger than it read: measured on prod, **15 of 34
active items (44%)** rendered EUR 0 in the app while the server held a value.
Per category — one_piece_tcg's tile said EUR 80.64 where the list summed to EUR
**0.00**; pokemon EUR 55.57 against EUR **15.00**.

Neither fix this note proposed was taken. "Items reads the server" would have
made `/portfolio/items` — which has **no LIMIT** — return the whole collection
to price twenty rows. A denormalised column needs a backfill, a maintainer and
a write-path benchmark, and can go stale.

The third option was a **view**: it executes with its owner's rights, so it can
read `price_predictions` past `price_predictions_deny_all`, and filters
`i.user_id = auth.uid()` so a caller sees only their own items. The client reads
it bounded by the page's ids (~0.55ms/item warm; ~11ms for a 20-item page).

**Note for anyone tempted by the obvious client-side fix:** `price_predictions`
grants SELECT to `authenticated` *and* denies every row via RLS. A direct read
from the app therefore **succeeds and returns `[]`** — a fix that changes
nothing and reports no error. That trap is why this sat open.

`v_item_values_v1` is now the single definition of item value. It was
EXCEPT-diffed in both directions against **both** live server expressions before
adoption (all four counts 0), so it could not move a number already on screen.
Gate: `npm run check:item-values`.

**Still to do (Stage 2):** repoint `/portfolio/items`, `category-breakdown` and
`/portfolio/overview` at the view. Until then the two server chains still order
`quick` and `catalog` differently — currently 2 items have both and they agree,
so it is latent, not live.

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

#### Settings → Edit Profile — built 2026-07-31

`ProfileEditSection` had been calling `PATCH /settings/profile` since it
shipped, but the route did not exist (**404**), `profiles` had no `bio` column,
and both public views hardcoded `NULL::text AS bio`. Live UI over nothing. Now
built end to end.

**Storage** (`20260731_profiles_bio_and_public_view.sql`): `profiles.bio text`
with `profiles_bio_length_check` (≤300 chars), and `user_public_profiles` now
selects `p.bio` instead of a NULL literal. `PublicUserProfileCard` and
`UserCollectionPreview` already render `{profile.bio && …}`, so they light up as
soon as it is non-null.

**Route** (`user_settings_router.py` → `PATCH /settings/profile`). Partial
update of the caller's own row; only `username` and `bio` are editable.

| Case | Result |
|------|--------|
| bio only / username only | 200, other field untouched |
| username already taken | **409 `USERNAME_TAKEN`** |
| same name, different case | **409** — enforced by `profiles_username_lower_key`, a UNIQUE index on `lower(username)` (added 2026-07-31). The handler also checks in code so the user gets a friendly 409 rather than a raw 23505, and `handle_new_user` does the same at signup — but **the database is the authority**, not those checks |
| bio > 300 chars | 422 with a clear message, not a 23514 surfaced as 500 |
| username with punctuation/spaces | 400 |
| empty payload | 400 |

Username uniqueness was case-SENSITIVE at the DB level until 2026-07-31
(`profiles_username_key`), so `Merle` and `merle` could coexist and only
application code prevented it — the same "constraint narrower than the code
assumes" shape as the currency/region/locale breakage. An index on
`lower(username)` already existed but was not UNIQUE; it now is. Proven by
bypassing every application check with direct SQL:
`duplicate key value violates unique constraint "profiles_username_lower_key"`.
Both compensating paths already handle the violation (`handle_new_user` falls
back to a nameless profile; `update_profile` maps it to 409 `USERNAME_TAKEN`).

`display_name` follows a rename **only while it mirrors the username** (the
signup trigger sets both). A display_name the user has deliberately diverged is
left alone — verified: renaming to `merle_probe2` kept `display_name = 'Merle S'`.

**The FE half that had to move with it:** `editBio` initialised to `''` and was
never populated, and the form posts whatever is in the field. That was harmless
while the route 404'd; the moment it persisted, opening the modal and saving
would have **wiped an existing bio**. `AuthProvider` now selects `bio` (added to
`Profile`) and the modal prefills both fields on open. If another editable
profile field is added, prefill it in the same place.

#### An empty update payload is a throw, not a no-op

`watchlist-builder`'s move up/down buttons called
`updateWatchlistItem(id, { sortOrder })`, but `watchlist_items` had no
`sort_order` column, so the provider deliberately dropped the field. That left
an **empty payload**, and the rest follows mechanically:

```
.update({})            -> PostgREST matches 0 rows
.select(...).single()  -> PGRST116 "The result contains 0 rows" (HTTP 406)
provider throws        -> the screen's catch rolls back the optimistic reorder
                       -> "Could not reorder. Please try again."
```

So reordering failed **every time**, visibly. Verified against prod 2026-07-31
by issuing the exact PATCH the provider produces — 406 before, 200 after.

Fixed on both sides:

- `sort_order integer` added (`20260731_watchlist_items_sort_order.sql`),
  nullable with no default so existing rows keep their priority ordering rather
  than all claiming rank 0. Index on `(user_id, sort_order NULLS LAST)`.
- `updateWatchlistItem` now writes it, and **returns the row unchanged instead
  of issuing an empty update** when no known field was supplied. That guard is
  the general fix: any future field the provider does not map would otherwise
  reproduce this exact failure.
- `listWatchlist` reads the real column instead of hardcoding `sortOrder: 0`.

**Rule: never let a mapper build an update payload that can come out empty.**
Either guard it, or the caller gets a throw for a write it believes succeeded.

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

#### E2E for the value chain and the reminder — what unit tests cannot reach

Two chains shipped in 2026-08-19 that no unit test can exercise, because both
depend on state a mock cannot fake:

| script | proves |
|---|---|
| `server/tests/e2e_value_provenance.py` | the label follows the value at every branch: typed → `user_estimate`, scan (`attrs.value_entry='app'`) → `app_estimate`, catalogue-linked → `catalog_model` OUTRANKS the estimate, `value_choice='mine'` → the member's number wins and withdrawing it hands the model back. Plus: `/portfolio/items` agrees with the view item by item, and an estimate contributes 0.00 to the board |
| `server/tests/e2e_grade_reminder.py` | one reminder per party 24h after completion, a second run sends NOTHING, a party who already rated is skipped, a trade completed 2h ago is untouched, and the deep link carries the offer |

Both run **from EC2** (the direct DSN does not resolve from a laptop) and delete
everything they seed, with a final check asserting that.

**The value E2E failed on its first run, and both failures were the TEST.** They
are worth knowing before writing another one:

- **`items.canonical_ref` is trigger-derived** (`trg_items_canonical_ref`, from
  `category || ':' || canonical_key`). Setting it directly in an INSERT is
  silently overwritten, so the catalogue join found nothing and the item read
  as `user_estimate`. Seed the two halves and let the trigger build the ref —
  the script now asserts it resolved.
- **asyncpg returns `id` as a UUID object**, so a dict keyed on seeded string
  ids missed every row and the endpoint looked like it had dropped them.
  `str()` both sides.

`grade_reminder_worker` had never sent a single notification before this — prod
holds no completed trade older than 24h, so every cycle correctly did nothing.
A worker that has only ever run on an empty set is a worker nobody has tested.
