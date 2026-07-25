# Sparrow Collect - Project Memory

> Renamed from CollectAI 2026-05-04 · Last refreshed 2026-05-19

## Overview
Sparrow Collect is a collector app for tracking collectibles (Pokemon, MTG, Funko, Warhammer, K-pop, etc.) with AI-powered scanning and valuation. **54 categories**, ~140K curated catalog items, **44 marketplace adapters**.

## Tech Stack
- **Frontend:** Expo SDK 54 (React Native 0.81) with Expo Router, TypeScript
- **Backend:** FastAPI (Python 3.12) with Supabase/PostgreSQL, asyncpg, partitioned monthly
- **ML:** 36 Ridge regression models (log-scale for high-variance categories), CLIP vision, OpenAI fallback
- **Payments:** RevenueCat (iOS IAP, shipped 2026-05-09); Stripe dormant for future web/Android
- **Theme:** Tiffany Blue (#81D8D0) accent, EUR currency, Roboto font

## Current state (2026-07-25)

- **Active branch:** `feature/creator-funnel-admin-dashboard`. iOS build 98 built locally (99 building); last on TestFlight was 96.
- **Apple:** Individual enrollment (Team `3DX8FBF7S6`), App ID `6767359453`, bundle `io.sparrowcollect.app`.
- **IAP:** RevenueCat Free + Pro (EUR 4.99/mo, EUR 39.99/yr) + Premium. **All current
  accounts and items are TEST data** (confirmed 2026-07-25) — treat prod data as disposable.
- **Builds are LOCAL ONLY** — `npm run build:ios:local`. Never `eas build` without `--local`.
- **Before any local build:** `npm run verify:prebuild` (tsc + seam tests + live Supabase contract).

### Production watchdog (added 2026-07-25)

`server/scripts/watchdog.py` — read-only daily report of what users did, what is
healthy, and what is silently failing. Cron `0 9 * * *` (server TZ Europe/Paris)
via `/opt/collectors/scripts/watchdog_daily.sh`, Telegram digest, JSON kept 30
days in `/opt/collectors/logs/`. See `docs/WATCHDOG.md`.

It reads **Supabase Logflare logs** (postgres/edge/auth) via the Management API,
which is the only layer that sees DB rejections and PostgREST failures — the EC2
journal cannot. On its first run it surfaced four production errors that every
app-side audit had missed.

### The failure mode this codebase is prone to

A writer and a reader that were never connected, plus a construct that turns
"not connected" into an empty result instead of an error: a bare
`except: pass`, Pydantic or Zod dropping an undeclared field, a CHECK constraint
narrower than the code, a LEFT JOIN yielding NULL, a `?? 0` default. Nothing
goes red, so a dead feature is indistinguishable from an unused one.

Three advisory audits exist for it — none blocks CI:
- `server/scripts/audit_orphan_tables.py` — tables read by code that nothing writes
- `server/scripts/audit_column_drift.py` — reader/writer on different columns
- `server/scripts/audit_key_overlap.py` — **joins whose two sides share no values**

**When something looks empty, check whether it is REJECTED before assuming it is
unused.** Look at Supabase > Logs > Postgres, not just the app journal.

### Identifier formats — read this before writing a JOIN

The 2026-07-25 incident: every query joining `items.canonical_key =
price_predictions.item_ref` matched zero rows, for every user, for ~4 months.
44 sites in 13 files. Portfolio value, category health, category stats,
timeseries, deep-dives, insights, exports and valuation-on-add were all
silently empty. **Nothing ever errored** — an empty join is a valid result.

| column | format | example |
|---|---|---|
| `items.canonical_key` | **bare** catalog key | `sm10-sm10-101` |
| `category_items.item_key` | **bare** | `sm10-sm10-101` |
| `items.canonical_ref` | **resolved price ref** (trigger-maintained) | `pokemon:sm10-sm10-101` |
| `price_predictions.item_ref` | **namespaced** always (0 bare rows in 1.7M) | `pokemon:sm10-sm10-101` |
| `price_prediction_daily.item_ref` | **namespaced** always | `pokemon:sm10-sm10-101` |
| `market_hits.item_ref` | **namespaced** always | `pokemon:ex8-ex8-13` |

Rules:
- Join predictions/market_hits with **`items.canonical_ref`**, never `canonical_key`.
- Join the catalog with **`items.canonical_key`** — `v_category_summaries_v1`
  depends on the bare form. Do NOT "normalise" canonical_key to namespaced.
- `ItemCreateRequest.canonical_key` documents a namespaced *example* but
  `/catalog/match` returns a bare key. That contradiction caused this bug.
  `canonical_ref` passes an already-namespaced key through without
  double-prefixing, so correcting the writer later is safe.
- Adding a text-key join? Declare it in `audit_key_overlap.py::PAIRS`.
- **No index on `canonical_ref`.** One was added, then dropped: EXPLAIN showed
  the planner seq-scans `items` (already filtered by `user_id`) and drives the
  join through the existing per-partition `price_predictions_*_item_ref_idx`.
  Identical plan and cost with and without it — governance rule 1 in
  `docs/DATA_SCALING_PLAN.md` is "default = refuse to add". Revisit only if a
  plan shows `items` as the expensive side.

### Loading states — the rule for any screen that fetches

Two bugs on 2026-07-25, both presenting as "stuck on a skeleton", both from the
same cause: **supabase-js ships NO per-request timeout.** A query fired while the
session is hydrating does not fail fast — it stalls behind the auth lock.

1. **Every direct Supabase read in a loading-gating path must use
   `withTimeout`** (`src/lib/withTimeout.ts`). chat/category/user/watchlist
   providers already did; `listItems` did not, so a stalled read left
   `isLoading` true forever with no error and nothing in the logs — and
   `logger.warn` is stripped in release builds, so it was invisible on exactly
   the builds where it mattered. Log timeouts with `logger.error`.
2. **Don't fire the first read until auth has hydrated.** Gate on
   `useAuthContext().loading`: `usePaginatedList` takes `enabled`, and
   index.tsx's focus effect returns early. This took cold-start auth-window
   burns from ~46 to 0.
3. **Any gate needs a deadline.** Gating on auth means a wedged session can pin
   the skeleton again by another route — `GATE_MAX_WAIT_MS` (5s) fetches anyway.

`usePaginatedList` enforces 1 and 3 for every caller (items, alerts, events, and
any list screen added later), so this cannot be reintroduced by a new screen.
Pinned by `__tests__/hooks/usePaginatedList.test.ts` — the three cases nobody had
covered were: a promise that never settles, a gate that opens, a gate that never
does. Wired into `verify:prebuild`.

**⚠️ Bounding an AUTH call is not automatically safe.** `withTimeout` is
`Promise.race`: it abandons the inner call without cancelling it. If a timeout
then leads to a SECOND concurrent auth op, two refreshes on one rotating
refresh-token trip Supabase's reuse detection and **revoke the session** — the
multi-week 401 saga ([[project_2026_07_11_auth_401_root_cause_lock]], why the
client uses `lock: processLock`). It is safe only when the bounded call neither
refreshes nor retries, and there is a recovery path. `httpClient.readAccessToken`
and `AuthProvider` follow that pattern; read `docs/AUTH_AND_WEB_DEPLOY.md` before
touching any of it.

**Known unbounded, deliberately NOT fixed yet** (swept 2026-07-25; 25 files have
unbounded `await supabase`, most harmless because nothing gates on them):

| file | why it is left | severity |
|---|---|---|
| `app/(auth)/login.tsx` (3), `register.tsx` (2), `forgot-password.tsx`, `reset-password.tsx`, `mfa-setup.tsx` (5) | all are AUTH ops — see the warning above. A hang here spins a button the user can see and retry, unlike a silent skeleton | medium, visible |
| `settings/ProfileEditSection.tsx` (2), `PrivacySettingsSection.tsx` (4) | plain PostgREST, safe to bound — just not done yet | low |
| `buildPaintProvider.ts` (15) | feature has 0 rows | low |

Fixed so far: `itemsProvider.listItems`, `usePaginatedList` (all callers),
`add-manual.tsx` (3 calls), `AuthProvider` (2 calls).

### The catalog ↔ price crosswalk

Not every category shares a namespace between catalog and predictions. Measured
catalog→price coverage ("can a user's item get a price?"):

| category | rows | priced | how |
|---|---|---|---|
| mtg | 25,407 seed | 98% | same slug both sides, no bridging needed |
| pokemon | 20,236 seed | 99% | same slug both sides |
| yugioh | 58,565 tcgcsv | **100%** | derived from the price source (per-PRINTING) |
| yugioh | 38,312 seed | 88% | via `catalog_price_refs` (per-CARD, approximate) |
| lorcana / digimon / one_piece_tcg | 22,042 tcgcsv | **100%** | derived from the price source |
| ⤷ same, old seed rows | 2,302 seed | 0% | superseded; see the seed/tcgcsv split below |
| lego, watches, whiskey, gunpla, warhammer, … (40+) | ~62,000 | **0%** | **no sold-comp source** — see below |

**The winning move was NOT a crosswalk.** Matching two namespaces was measured
and rejected (name-only was 224-of-226 ambiguous for lorcana; adding set gave
8.2% / 1.3% / 0.0%). Instead `import_tcgcsv.py --catalog` DERIVES catalog rows
from the same products that produce the prices, so
`category || ':' || item_key == price_predictions.item_ref` holds **by
construction** — which is exactly why pokemon/mtg never needed bridging. Runs
daily via `run_once(catalog=True)`, gated to `CATALOG_CATEGORIES`.

`catalog_price_refs` remains for the **seed** yugioh rows only, built by
`pipelines/build_catalog_price_crosswalk.py`. `items.canonical_ref` is resolved
by `trg_items_canonical_ref`, preferring the direct key (printing-exact) and
falling back to the crosswalk.

**Seed vs tcgcsv:** the old `source='seed'` rows still exist alongside the
derived ones and are mostly unpriceable. Do NOT bulk-delete them — 7.6% are
non-card merchandise (figures, Digivices) that tcgcsv cannot cover, and user
items point at seed keys. Deduplicate in the browse query using `source`. An item
linked to a seed key shows €0 even though its tcgcsv twin is priced — that is the
known `Azurite Sea Booster Box` case.

**The 62,000 gap is ONE stubbed function, not a sourcing problem.** The scraper
runs and collects ~74k hits/day for those categories (lego 26,903, warhammer
18,477 …), but `ebay_caller.py:387 sold_comps()` **returns `[]`** pending
migration to the Marketplace Insights API, so everything falls back to the Browse
API = active listings, `is_listing = TRUE`, and `valuation_worker.py:279`
excludes them. A listings→sold haircut is NOT calibratable: only 205 refs have
both, and the observed ratio is backwards (1.32–1.60).

**Accuracy limit — do not present yugioh crosswalk prices as printing-exact.**
The passcode price is per CARD, so every printing of a card shows the SAME
value: a scarce 1st-edition and a common reprint are indistinguishable. Stored
with `method='name_slug'`, `confidence=0.75` so it can be filtered later.
Ambiguous names (8) are skipped, never guessed.

**Rebuilding the crosswalk does NOT refire the trigger** — the builder
re-touches `items` afterwards. If you change `catalog_price_refs` by hand, run
`UPDATE items SET canonical_key = canonical_key WHERE canonical_key IS NOT NULL`.

**Structural checks cannot catch this class.** The table existed, was populated,
the column names matched, the SQL was valid, the endpoint returned 200. Only
comparing the VALUES on each side reveals it — which is all `audit_key_overlap.py`
does. Coverage caveat: even with the correct join only ~13% of predicted refs
are catalog-reachable; TCG categories key predictions by TCGplayer product id
(`lorcana:tcgplayer:702699:normal`) while the catalog uses set-slugs, so
lorcana/digimon/one_piece_tcg sit at 0% until an id crosswalk exists.

## Key Files
- `app/(tabs)/_layout.tsx` - Main tab navigation (5 visible tabs: Home, Items, Add, Events, Marketplace; wishlist + search are hidden routes)
- `app/(tabs)/index.tsx` - Portfolio dashboard with line chart
- `app/(tabs)/items.tsx` - Item list with search/filter, multi-select, bulk operations
- `app/(tabs)/add.tsx` - QuickScan and manual add entry
- `app/quickscan.tsx` - Camera capture flow
- `app/item/[id].tsx` - Item detail with price bands
- `app/analytics.tsx` - Portfolio insights dashboard
- `src/data/DataProvider.ts` - Data interface
- `src/data/MockDataProvider.ts` - Mock implementation
- `src/taxonomy/` - Category classification system

## Data Flow
```
UI Components → dataProvider (singleton)
  ├─ MockDataProvider (default, for development)
  └─ SupabaseDataProvider (mode="real", for production)
```

---

## UI/UX Improvement Roadmap

### Priority 1: Core Flow Friction Reducers

#### 1.1 "I Got It!" Wishlist → Portfolio Flow ✅ DONE
- [x] Add "Mark as Acquired" button on wishlist item detail
- [x] One-tap creates item in portfolio with pre-filled data
- [x] "Congrats!" animation on acquisition
- [x] Prompt for actual purchase price (feeds ML model)
- **Files:** `app/(tabs)/wishlist.tsx`, `src/data/DataProvider.ts`

#### 1.2 QuickScan Result Enhancement ✅ DONE
- [x] Price confidence gauge/meter visualization
- [x] "Why this price?" expandable explanation section
- [x] Quick-edit inline for name/category before saving
- [x] "Scan Another" button for batch sessions
- **Files:** `app/item/[id].tsx`, `src/components/PriceConfidenceGauge.tsx`

#### 1.3 Category Drill-Down from Item Detail ✅ DONE
- [x] Tappable category pill → category store
- [x] "See X similar items" link
- [x] "Missing from this set" teaser
- **Files:** `app/item/[id].tsx`, `app/categories/[categoryId].tsx`

### Priority 2: Engagement & Delight

#### 2.1 Portfolio Milestones & Achievements ✅ DONE
- [x] Achievement badges: "First item", "10 items", "€1000 portfolio"
- [x] Streak tracking for daily activity
- [x] Tier system (bronze, silver, gold, platinum)
- **Files:** `src/lib/achievements.ts`, `src/components/AchievementBadge.tsx`

#### 2.2 Visual Collection Grid (Gallery View) ✅ DONE
- [x] Toggle between list/grid on Items tab
- [x] Pinterest-style image grid
- [x] Tap to zoom with lightbox modal
- **Files:** `app/(tabs)/items.tsx`, `src/components/ItemGalleryGrid.tsx`

#### 2.3 Price Alert Animations ✅ DONE
- [x] Pulse animation on significant value change
- [x] Red/green micro-animation on price delta
- [x] "Hot" badge on trending items
- **Files:** `src/components/PriceDeltaBadge.tsx`

### Priority 3: Discovery & Social

#### 3.1 "Collectors Like You" Recommendations
- [ ] "People who collect X also collect Y" on category store
- [ ] Surface overlapping collections from public profiles
- [ ] "Follow Collection" feature
- **Files:** `app/categories/[categoryId].tsx`, `src/data/DataProvider.ts`

#### 3.2 Event Integration Improvements ✅ DONE
- [x] Native calendar integration (iOS/Android)
- [x] Countdown timers for upcoming drops
- [x] "Set Reminder" with push notification
- [x] Separate upcoming/past events sections
- **Files:** `app/(tabs)/events.tsx`, `src/lib/calendar.ts`, `src/components/EventCountdown.tsx`

#### 3.3 Marketplace Trust Integration
- [ ] "For Sale" listings on item detail
- [ ] Trust score badge on sellers
- [ ] "Price Check" comparing value to market
- **Files:** `app/item/[id].tsx`, `src/components/MarketListings.tsx` (new)

### Priority 4: Power User Features

#### 4.1 Bulk Operations ✅ DONE
- [x] Multi-select mode on Items tab
- [x] Bulk category reassignment
- [x] Bulk export selected items
- [x] Bulk delete with confirmation
- [x] Long-press to enter multi-select
- **Files:** `app/(tabs)/items.tsx`, `src/hooks/useMultiSelect.ts`

#### 4.2 Advanced Filters & Sorting ✅ DONE
- [x] Filter by: condition, price range, category
- [x] Sort by: value (high/low), name (A-Z/Z-A), recently added
- [x] Save filter presets with names
- [x] Collapsible filter sections
- **Files:** `app/(tabs)/items.tsx`, `src/components/FilterSheet.tsx`

#### 4.3 Portfolio Insights Dashboard ✅ DONE
- [x] Category breakdown pie chart
- [x] Best/worst performers
- [x] Liquidity score
- [x] Diversity index
- [x] Portfolio tier badges
- **Files:** `app/analytics.tsx`, `src/components/PortfolioPieChart.tsx`

### Quick Wins ✅ ALL DONE

| Feature | Status | File |
|---------|--------|------|
| Haptic feedback on save/delete | [x] | `src/lib/haptics.ts` |
| Pull-to-refresh on all lists | [x] | Items, Events, Wishlist |
| Empty state illustrations | [x] | `src/components/EmptyState.tsx` |
| Skeleton loaders | [x] | `src/components/Skeleton.tsx` |
| Swipe-to-delete | [x] | `src/components/SwipeableRow.tsx` |
| Long-press context menu | [x] | Multi-select mode on Items |

---

## Implementation Notes

### Completed UI/UX Sprint (2026-02-02)
- [x] Full UI/UX improvement roadmap implemented
- [x] 12 major features completed
- [x] 6 quick wins implemented
- [x] All core components created and integrated

### New Components Created
- `src/components/PriceConfidenceGauge.tsx` - Visual confidence meter
- `src/components/PriceDeltaBadge.tsx` - Price change animations
- `src/components/ItemGalleryGrid.tsx` - Pinterest-style grid
- `src/components/AchievementBadge.tsx` - Achievement display
- `src/components/EventCountdown.tsx` - Countdown timer
- `src/components/FilterSheet.tsx` - Advanced filter modal
- `src/components/EmptyState.tsx` - Empty state illustrations
- `src/components/Skeleton.tsx` - Loading skeletons
- `src/components/SwipeableRow.tsx` - Swipe gestures
- `src/components/PortfolioPieChart.tsx` - Category breakdown

### New Utilities Created
- `src/lib/haptics.ts` - Tactile feedback
- `src/lib/calendar.ts` - Calendar/notification integration
- `src/lib/achievements.ts` - Achievement system
- `src/hooks/useMultiSelect.ts` - Multi-selection hook

### Completed Cleanup (2026-02-02)
- [x] ErrorBoundary integrated into root layout
- [x] Comprehensive .env.example documentation
- [x] .gitignore updated for backup files
- [x] Logger utility created (src/lib/logger.ts)
- [x] Console.log replaced with logger in critical paths

### Taxonomy System
- Version: 2026.02.02
- Categories: Pokemon, MTG, Yugioh, Funko, Lorcana (Phase 1) + more
- Collection tags: BTS, Taylor Swift, Disney, Star Wars, etc.
- Deterministic mapper with confidence scores

### Environment Variables
See `.env.example` for full documentation. Key vars:
- `EXPO_PUBLIC_SUPABASE_MODE` - "mock" or "real"
- `API_SHARED_SECRET` - Backend API authentication
- `DB_ENABLED` - Database connectivity toggle
