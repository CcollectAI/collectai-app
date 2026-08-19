# Sparrow Collect - Project Memory

> Renamed from CollectAI 2026-05-04 · Last refreshed 2026-08-19

## Current state (2026-08-19)

### ⛔ Check your own new code BEFORE calling it done (2026-08-19)

Asked for after an audit found **three bugs in code written the same hour**, one
already deployed. Five real defects landed that day and **not one was caught
while writing** — gates or an explicit audit caught them all. The cause is a
single habit:

> The happy path is verified against data that CANNOT DISCRIMINATE.

| defect | why the check passed |
|---|---|
| `ORDER BY documented_pct, documented_count DESC` — DESC binds to the LAST column, so the percentage sorted ASCENDING and the least-documented member ranked #1 | every member was at 0%; everything tied, so direction was unobservable |
| `Math.abs(50.01 - 50) >= 0.01` is **false** — a real one-cent difference never prompted | tested €62 vs €50, nowhere near the boundary |
| `setMetric` inside the effect that lists `metric` as a dep (self-cancelling) | only tears down on a dep change, never on first render |
| stale `attrs` spread into a **merge** endpoint (lost update) | one edit per session looks correct |
| Home would have called a whole portfolio "estimated" when no item carried a provenance | prod data had provenance, so the empty case never rendered |

**The pass to run before writing "done":**

1. Ask *what data would make this look right while being wrong* — uniform,
   empty, all-zero, single-row, exactly-at-the-boundary — then test that.
2. **A sort direction, threshold or comparison cannot be proven on uniform
   data.** A 3-row `VALUES` list against prod costs nothing and settled the
   ranking bug in one query.
3. Money in **cents**, never an epsilon.
4. Read the endpoint before assuming merge vs replace, then send the minimum
   payload.
5. Two literals that must agree is a bug waiting (a page size and the guard
   that reads it) — collapse them.
6. "We don't know" must never render as a claim: no provenance is not "all
   estimated", no comps is not "worth 0".
7. Measure the cost you added (DATA_SCALING_PLAN rule 2) instead of assuming it
   is small.

### Value provenance — what a number on screen is allowed to claim

`v_item_values_v1` now returns **`value_source`** beside `value_eur` (applied
to prod, schema.lock regenerated, preflight PASS). The app renders it as a chip
on item detail and the items list; the leaderboard ranks on the **market-backed
subset only**. Full detail: docs/ARCHITECTURE.md.

**The finding that drove it: the column names lie.**

| column | name suggests | actual only writer |
|---|---|---|
| `quick_predictions` | QuickScan output | `write_quick_valuation` — the daily catalogue rollup. **Comp-backed** |
| `items.predicted_price_eur` | model output | add-manual's **"Estimated value" text field** |

So the chain's link 3 was a hand-typed guess ranked ABOVE `estimated_value`,
where every other writer puts one — a later correction could be outranked by
the original and never show. `estimated_value` is now THE user-estimate column;
`predicted_price_eur` is read-only legacy.

It is now READ by four surfaces, each with its own rule: the chip labels it,
the **leaderboard ranks on the market-backed subset only**, **analytics splits
into three numbers** (paid / market / estimated), and **Home includes the
estimate and says how much of the headline it is**. An unknown source counts as
an estimate everywhere — the side that under-claims.

**A member may override the model, and it actually wins.** Manual add used to
replace their number silently (save, then `revalueItem` writes a catalogue
valuation into the TOP of the chain). The item screen now asks, after the save,
and `attrs.value_choice = 'mine'` sits ABOVE the model in the view — otherwise
"keep mine" could not be honoured at all, since both prediction tables outrank
`estimated_value` and the catalogue model is global data, not the member's row.
Applied to prod; proven byte-identical for anyone who has not chosen, and
proven to flip (74.80 catalog_model → 12.34 user_estimate → restored) for one
who has.

Three write-path defects fixed with it: `updateItem` accepted `price` and
mapped it to nothing (a trap for the offline queue, which replays queued args
verbatim); `persistQuickscanDraft` posted four fields and dropped the scan's
estimate and condition, so a scanned item saved with no value; and
`app/item/[id].tsx` derived a THIRD value chain that skipped both prediction
tables.


**Trade ratings are now READ somewhere.** Two-sided rating has existed since
Stage 2 (`member_grades`, either party, anchored to a completed offer). What
was missing was every surface that should show it. Full writeup:
`docs/P2P_MARKETPLACE_SPEC.md` §12 and `docs/alerts-and-insights.md`.

Four bugs found while wiring it, **all four instances of classes this file
already names** — which is the point of naming them.

| What | Class | Where |
|---|---|---|
| Dossier valuation + 90-day chart empty for EVERY item, every user — bound the **bare** `canonical_key` against the namespaced `item_ref` | identifier formats (below) | `dossier_agent.py` |
| Dossier printed **no grade for a graded item** — read `attrs["grade"]`, which no writer writes | reader/writer never met | `dossier_agent.py` |
| Every server-sent `deep_link` is RELATIVE; `new URL()` throws on those into a catch that logs and returns — **6 senders, all with a dead tap** | dead-by-wiring | `usePushNotifications.ts` |
| `seller_collection_size` counted **archived** items, crediting a seller for what they had already sold | archived-as-owned | `p2p_listing_router.py` |

The first two are in `dossier_pdf`, a **Pro** feature. The third is the reverse
of the usual shape: the SEND side was correct and the RECEIVE side dropped it,
so nothing server-side looked wrong and the notification visibly arrived.

**The fourth was found BY a gate that had been blind to the query.** Splitting
the listing SQL around a shared fragment turned one string literal into three,
and `check:archived` reports per literal — the detail query had been passing
only because its `WHERE l.id = $1` made the whole literal read as a by-id
lookup. Keeping gates literal-scoped is what made it visible.

### The server test suite was 31-red, and it was mostly EVIDENCE

31 failures → **7** (3,763 passing). Almost none was a broken product; they
were stale *pins*, and several were pinning behaviour that had been
deliberately changed. **The doc decides, not the test** — "fixing" the code
until the suite went green would have reopened real bugs:

| pinned | truth | if you had believed the test |
|---|---|---|
| free `max_mandates == 3` | **0** since 2026-07-31 | reopens the deep-link bypass and makes the paywall advertise mandates the buyer gets none of |
| pro `advanced_analytics is False` | **True** since 2026-07-28 | sends a paying Pro user to the paywall instead of `/analytics` |
| `/items-export/overview` header `id,title,…` | the 12-col round-trip schema | breaks export → edit → re-import |
| pricecharting is disabled | **re-enabled 2026-07-22** (keyless public-site scrape) | drops the only sold comps retro_games has |
| eBay `sold_comps` parses a Finding response | **stubbed `return []`** since 2026-04-26 | resurrects a revoked API and flaps the breaker shared with Browse |

Two mechanisms worth keeping:

- **`items_export` now pins `EXPORT_COLUMNS == IMPORT_COLUMNS`.** They are two
  lists in two files kept in step by a *comment*; nothing enforced it, so a
  column added to one side would silently make every exported file
  un-importable.
- **A mock that routes on SQL TEXT cannot see which VALUE was bound.** The
  `canonical_ref` fix passed its first mutation test for that reason. The mock
  now records `(sql, args)` and the test asserts the ref — structure could
  never have caught a bare-vs-namespaced key
  (`learning_validate_values_not_just_structure`).

⚠️ **Undeclared parsing dependencies.** `booth`, `suruga_ya` and
`yahoo_auctions` `from bs4 import BeautifulSoup` and ask for the **lxml** tree
builder; `requirements.txt` declares **neither** — both arrive transitively via
`crawl4ai`. `suruga_ya` and `yahoo_auctions` are LIVE, and both failure modes
degrade to "0 hits" (bs4 missing → warning + `[]`; lxml missing →
`FeatureNotFound` swallowed by `except Exception`). If that transitive
dependency moves, two sources go quietly dry with nothing red. Declare both,
pinned to what the box already has.

**Not deployed, not device-walked.** The server half needs
`scripts/deploy_to_ec2.sh` + the 9 preflight stages run manually, and the whole
chain — completed trade → push → tap → rate → the number on the tile and the
profile — has not been walked on a device.

## Current state (2026-08-10)

**iOS build 125 is on TestFlight** (uploaded 20:17 CEST, submission
`001c0dc3`). 121 and 123 were built locally and **never submitted** — see
"Submission status is not TestFlight status" below.

Seven fixes landed today; four are instances of classes this file already names.

| What | Class | Where |
|---|---|---|
| Category "average value" counted unpriced items as **EUR 0** | `unknown-as-zero` | `portfolio_router.py` — DEPLOYED |
| Watchlist rendered empty when the read fired before auth | loading-states §2 | `(tabs)/wishlist.tsx` |
| Member-listings rail 401'd before auth — **same class, new code, same day** | loading-states §2 | `(tabs)/marketplace.tsx` |
| XP printed `12.500` on a Dutch phone, `12,500` on a US one | device locale ≠ `user_settings.locale` | `leaderboard.tsx` |
| Unified search reachable from **nowhere** | dead-by-wiring | `(tabs)/search.tsx` |

### An unpriced item is not a zero-euro item (DEPLOYED)

`/portfolio/category-stats` ended its COALESCE chain in `0`, so `AVG` counted
every unpriceable item as a EUR 0 **sample in the denominator**. For the 40+
categories with no sold-comp source (~62k rows at 0% priced) the reported
average collapsed toward zero. `avg_value` is replaced by a **median plus
min/max**; a category with nothing priced returns `null`, not `0.0`, and reads
"not yet priced".

**`check-silent-failures.mjs` did not catch it** — the checker reads JS/TS and
this was SQL inside a Python string. Every new AXIS needs its own sweep; this is
the third time that sentence has been written here.

⚠️ **Build 125 predates the FE half.** It still reads `avg_value`, which the
deployed server no longer returns. `formatPrice` renders `—` for null so it
degrades rather than crashes, but the analytics screen shows "avg —" until the
next build.

### Submission status is not TestFlight status

`eas submit` runs fastlane pilot with `skip_waiting_for_build_processing:true`
and `"groups":[]`, so a submission reads **FINISHED the moment Apple accepts the
bytes** — before processing, and without assigning it to a tester group. For
`--path` submissions of local IPAs, EAS also records **no build number at all**
(`appStoreConnectBuildUpload` is null), and `build:list` only shows cloud
builds. So EAS cannot answer "which build did I last send to Apple?"

Authoritative sources are only App Store Connect and Apple's processing email.
Keep renaming the shipped artifact to `*-uploaded.ipa` — on 2026-08-10 that
filename was the only surviving record that 120, not 121 or 123, was the last
build submitted.

### A feature can be complete, correct, and reachable from nowhere

Distinct from the silent-failure class below, and not caught by any existing
gate. Three found on 2026-08-10:

- **Unified search** (`app/search.tsx`, `GET /search/unified`, trigram index,
  built the day before) — **zero** call sites pushed to `/search`, while
  `(tabs)/search.tsx` redirected to a marketplace screen whose search never
  reads `category_items`. Reported as "rolex daytona is not in the catalogue".
  It was: 12 Daytona rows, 77 Rolexes, 1,416 watches.
- **`WatchlistWidget`** and **`CategoryLeaderboardSection`** — both exported
  from a barrel, both rendered by no screen.

`check-dead-nav.mjs` reports PASS on all of it: it asks whether a router target
**resolves**, never whether anything **reaches** it.

**`npm run check:reachable` now asks the other half** (added 2026-08-12,
`scripts/check-unreachable-screens.mjs`): it builds the push/`Link`/`Redirect`
graph over `app/**` and reports any screen with no inbound edge. Proved against
`app/market-hub.tsx` — restore it with its entry point repointed and the gate
names it. **Advisory (exit 0)** like `audit_orphan_tables.py`, because it
currently reports a real backlog: `/franchise/[id]`, `/sell/dashboard`,
`/sets-to-complete`, `/twitch` are all live screens nothing navigates to. Flip
`--strict` and add it to `verify:prebuild` once that list is empty.

It does **not** catch the second half of the 2026-08-10 finding: a component
exported from a barrel and rendered by no screen is not a route, so nothing in
the route graph sees it. That gap is still open.

**`check:params` resolves a push target to its route FILE.** A one-line
re-export (`export { default } from '../search'`) therefore reads as "that route
reads: (none)". Push to the file that actually calls `useLocalSearchParams`, or
the contract stops being checkable.

## Overview
Sparrow Collect is a collector app for tracking collectibles (Pokemon, MTG, Funko, Warhammer, K-pop, etc.) with AI-powered scanning and valuation. **54 categories**, ~140K curated catalog items, **44 marketplace adapters**.

## Tech Stack
- **Frontend:** Expo SDK 54 (React Native 0.81) with Expo Router, TypeScript
- **Backend:** FastAPI (Python 3.12) with Supabase/PostgreSQL, asyncpg, partitioned monthly
- **ML:** 36 Ridge regression models (log-scale for high-variance categories), OpenAI Vision + heuristic fallback
- **Payments:** RevenueCat (iOS IAP, shipped 2026-05-09); Stripe dormant for future web/Android
- **Theme:** Tiffany Blue (#81D8D0) accent, EUR currency, Roboto font

## Current state (2026-08-09)

- **A completed P2P trade now MOVES THE OBJECT.** `_settle_completed_trade`
  (`p2p_offers_router.py`) retires the seller's item (decrements if they hold
  several), mints the buyer a NEW row — never the seller's, which would hand
  over their `purchase_price` / `purchase_notes` / `cost_basis` — releases the
  soft reservation, and declines + notifies every other live offer. Deployed and
  verified 40/40 by `server/tests/e2e_p2p_stage2.py` against prod.
  - **`for_sale` is NOT written there.** Trigger `trg_sync_item_for_sale`
    recomputes it from the live listing set, scoped to `marketplace_id='sparrow'`.
    A first draft duplicated that rule *without* the scope; a prod census proved
    the trigger already handled it. Two impls of one rule is the bug, not the fix.
  - Archive, not delete: **29 tables FK to `items.id`, mostly ON DELETE CASCADE**
    — including `marketplace_listings`, `price_ground_truths` and
    `verified_sales`. Deleting a sold item would erase the sale and the
    calibration data the completion had just written.
- **`items.archived` is now honoured** — and `/archived` exists so it is
  reversible. Archiving is reachable from a SWIPE, so hiding without a restore
  route would have been a one-way trapdoor. Gate: `npm run check:archived`.
  - Achievement counters (`items_router`, `intake_router`) are deliberately
    exempt: milestones are LIFETIME activity, and archiving is not un-scanning.
  - Aggregates (`data_moat`), the admin dashboard, and listing browse carry
    `archived-exempt:` markers stating why.
  - **The valuation/learning loop is unaffected either way** — it runs off
    `market_hits` and `price_ground_truths` keyed by `item_ref`/`item_id`, and a
    flag flip cascades nowhere.

- **iOS build 121** built locally; **120 is on TestFlight**. Backups kept as
  `builds/sparrow-ios-local-b120-uploaded.ipa` / `-b121.ipa`, because
  `build:ios:local` overwrites `sparrow-ios-local.ipa` in place.
- **`appVersionSource: remote`** — `app.json`'s `ios.buildNumber` (101) is NOT
  what ships. Read `CFBundleVersion` out of the built `.ipa`.
- **Expo Go cannot host this app.** `react-native-purchases` and
  `@sentry/react-native` are hard static imports, so the sim needs a native dev
  build: `SENTRY_DISABLE_AUTO_UPLOAD=true npx expo run:ios --device "iPhone 17"`.
  Without that env var the build dies at the Sentry phase with *"An organization
  ID or slug is required"* — the same reason `eas.json`'s dev profiles set it.
- **DAC7 is inform-only, deliberately.** Counters + notice + a member-facing
  screen exist; there is **no** column anywhere for a TIN, address or IBAN and
  that is a decision, not a gap. `marketplace-terms.tsx` §6, the notice in
  `_dac7_accrue`, and `app/tax-reporting.tsx` must say the same thing — change
  one, change all three. Open (legal, not code): whether registration is
  required with only excluded sellers, and whether the 5% event-ticket fee
  (`terms.tsx:154`, `:173`) pulls events in.

### Earlier (2026-07-25)

- **Active branch:** `feature/micro-interactions-haptics`. iOS build 100 built locally 2026-07-25 (`builds/sparrow-ios-local.ipa`); last on TestFlight was 96.
- **Apple:** Individual enrollment (Team `3DX8FBF7S6`), App ID `6767359453`, bundle `io.sparrowcollect.app`.
- **IAP:** RevenueCat Free + Pro (EUR 4.99/mo, EUR 39.99/yr) + Premium. **All current
  accounts and items are TEST data** (confirmed 2026-07-25) — treat prod data as disposable.
- **Builds are LOCAL ONLY** — `npm run build:ios:local`. Never `eas build` without `--local`.
- **Before any local build:** `npm run verify:prebuild` (tsc + seam tests + live Supabase contract).
- **Android (assessed 2026-07-31):** the app builds and runs on Android — verified on a
  device, no crash. `npm run build:android:local` (.aab for Play) /
  `npm run build:android:apk` (installable, same shipping config). What is missing is
  console setup only: Play enrolment + service account, `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY`,
  FCM. **Run `npm run preflight:android` before any Android build or submit** — it checks
  all of those plus the Android-only code traps below. See `docs/ANDROID_LAUNCH.md`.

### The Android variant of the failure mode below

**The one that is NOT silent — and is launch-blocking.** `accessibilityRole="tabbar"`
is iOS-only; on Android react-native throws `IllegalArgumentException` while creating
the view, a **FATAL EXCEPTION**. One line in `src/components/QuickNavBar.tsx`, mounted
by **38 screens**, so the entire app past the five root tabs died on Android. Two
logged-out launch tests both said "no crash". **Only a real authenticated session
walking real screens found it** — see [[feedback_never_call_app_ready_without_e2e_verify]].
Use `"tablist"` for a tab container; the gate now validates every role value.

Android gaps in this codebase are otherwise all the same shape: **a platform-specific
path that degrades to a no-op instead of an error**, so the app quietly does less on
Android while iOS looks fine and nothing goes red. Found 2026-07-31, all silent:
`SafeAreaView` imported from `react-native` (iOS-only, a plain `View` on Android);
`<Modal>` without `onRequestClose` (back button dead on Android only);
`expo-store-review` never installed under a guarded `require`; the RevenueCat Android
key unset so the paywall could not sell; FCM absent so push tokens always threw.
`scripts/preflight_android.mjs` is the checker — extend it rather than fixing the next
one by hand.

### Production watchdog (added 2026-07-25)

`server/scripts/watchdog.py` — read-only daily report of what users did, what is
healthy, and what is silently failing. Cron `0 9 * * *` (server TZ Europe/Paris)
via `/opt/collectors/scripts/watchdog_daily.sh`, Telegram digest, JSON kept 30
days in `/opt/collectors/logs/`. See `docs/WATCHDOG.md`.

It reads **Supabase Logflare logs** (postgres/edge/auth) via the Management API,
which is the only layer that sees DB rejections and PostgREST failures — the EC2
journal cannot. On its first run it surfaced four production errors that every
app-side audit had missed.

### Partition retention vs `schema.lock.json` (2026-08-02)

`schema.lock.json` no longer locks partition CHILDREN — `regen_schema_lock.py`
filters `c.relispartition`. Children are created by pg_cron on the 25th and
dropped by `partition_drop_worker`; locking them made routine retention look
like schema drift. Before the fix, dropping `market_hits_y2026m07` +
`price_history_y2026m07` (2.9 GB, correctly exported to S3) left
`preflight_schema_lock.py` failing — and that gate **only runs at startup**, so
the API stayed up and the *next* bake restart would have hard-downed it, hours
after the unrelated-looking cause. The partitioned PARENTS are still locked in
full. Full writeup + the verification protocol for a destructive drop:
`docs/DATA_SCALING_PLAN.md` § 10.

**S3 checks against the warehouse bucket must `source /opt/collectors/.env`
first.** The EC2 instance role has no access; the export worker uses env
credentials. A bare `aws`/`boto3` call on the box reports `AccessDenied` and
looks exactly like missing data.

### The failure mode this codebase is prone to

A writer and a reader that were never connected, plus a construct that turns
"not connected" into an empty result instead of an error: a bare
`except: pass`, Pydantic or Zod dropping an undeclared field, a CHECK constraint
narrower than the code, a LEFT JOIN yielding NULL, a `?? 0` default. Nothing
goes red, so a dead feature is indistinguishable from an unused one.

**Enumerate this class mechanically; never triage it by judgment.** The pattern
that made bugs surface late was: fix the reported instance, hand-triage the
rest, declare done — then the user hits the next one. `npm run verify:silent`
(`scripts/check-silent-failures.mjs`) turns each variant into a check:

| class | what it renders |
|---|---|
| `ungated-demo-data` | invented data as the user's real data |
| `capped-aggregate` | a partial number as the whole truth |
| `unchecked-write` | success when the write failed |
| `unknown-as-zero` | "unknown" as "zero" |
| `swallowed-catch` | no trace at all |
| `prod-invisible-log` | a trace stripped from release builds |

**Each new AXIS needs its own sweep — the existing gates are axis-shaped and
report PASS on everything outside their axis** (2026-08-09). Three more classes,
each found by a user report and each previously invisible to every check:

| gate | class it catches | why nothing else saw it |
|---|---|---|
| `npm run check:effects` | an effect that lists a state **it writes** in its own dep array, so React tears it down and its `.then`/`.catch` are disarmed mid-flight | not an unbounded await — the request SUCCEEDS. `app/offers.tsx` carrier picker was dead on every open while the endpoint served 9 carriers to curl |
| `npm run check:params` | a route param pushed but never read by the destination | `check-dead-nav.mjs` contains the string `params` **zero times** — it only asks whether the route file exists. `typedRoutes` is on but types params as `UnknownInputParams`, an OPEN record, so `prefillTitle` on `/add-manual` is legal TS. 5 live dead handoffs |
| `npm run i18n:parity` | a key in `en.json` missing from another locale | `i18n:check` finds UNWRAPPED strings — it polices the code, not the files. `fallbackLng: 'en'` means a missing key renders **English**, silently. en had 597 keys, all 6 others had 424 |
| `npm run check:archived` | a read of `items` that counts **archived** rows as owned | an archived row is a VALID row, so nothing errors. `archived` was written by swipe/bulk archive and respected by 8 VIEWS, but by **no read of the table** — the bulk dialog promised "archived items will be hidden from your active collection" and the next refresh brought them straight back ([[learning_a_written_promise_to_users_is_a_spec]]). 50 reads, all silent |
| `npm run check:reachable` **(advisory)** | a screen with **no inbound navigation edge** — it exists, compiles, resolves, and cannot be arrived at | `check-dead-nav` asks the opposite question and passes forever. The Market hub's three signal modules were unreachable for a day; `/franchise/[id]`, `/sell/dashboard`, `/sets-to-complete` and `/twitch` still are. **Not in `verify:prebuild`** — it reports a backlog, and a blocking gate would wedge every deploy until that backlog is zero (same reasoning as `audit_orphan_tables.py`) |

All except `check:reachable` are wired into `verify:prebuild`, and each was
proven to fail before it was fixed.

**Writing a graph-shaped gate: match the literal, not the call.** Two false
positives had to be killed before `check:reachable` was trustworthy, and both
generalise — an edge inside a **ternary**
(`router.push(cond ? '/purchase' : '/subscription')`) is invisible to any
call-shaped regex, and a **template literal carrying a query**
(`` `/events/x?eventId=${id}` ``) dies on a character class that stops at `?`.
A gate that cries wolf stops being read, which costs more than the bug. `check:params` compares against the target's **declared** params, not
substrings — a substring version passed a genuinely dead `mode: 'watchlist'`
because the word "mode" appears elsewhere in the file.

The first four are at 0 and each was proven to fail before being fixed. Two real
bugs it caught: `fetchPortfolioSeries` returned a fabricated €1200→€2050 curve
ungated in production (its `DEMO_ITEMS` sibling *had* been gated — the fix was
applied to one of three and never swept), and `usePortfolioInsights` summed a
list capped at `limit: 50` to produce the portfolio total.

Intentional swallows carry a `best-effort:` marker stating why, so a decision is
distinguishable from an oversight. Remaining and reported, not hidden: 91
swallowed catches (none touching a backend call) and 181 logging only via
warn/info.

**One logger, not two.** `@/utils/logger` used to strip `warn` while
`@/lib/logger` printed it; 102 files imported one and 44 the other, so whether a
failure survived into a release build depended on which import a file happened
to have. Collapsed to one implementation; every level is retained in a bounded
ring buffer readable via `getRecentLogs()`, so a failure is recoverable even
when it is not printed.

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
| `purchase_mandates.canonical_ref` | **namespaced**, nullable (2026-08-12) | `pokemon:base1-base1-1` |

Rules:
- Join predictions/market_hits with **`items.canonical_ref`**, never `canonical_key`.
- **A mandate stores ONLY the namespaced form.** `purchase_mandates` joins
  `price_predictions.item_ref` and nothing else, so it needs one column, not the
  bare/namespaced pair `items` carries. The API takes a BARE `canonical_key`
  from the picker and builds the ref from the item's own `category_items` row —
  never from the request body and never from the mandate's `category` field,
  because a ref with the wrong prefix matches zero rows and returns an empty
  join instead of an error. NULL = a free-text mandate, valued by an
  ILIKE-on-query fallback that is deliberately **not** trusted for money:
  `value_summary.deal_savings` counts keyed mandates only.
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

**4. The bound now lives on the CLIENT, not the call site** (2026-07-25).
Fixing call sites one at a time did not converge. A hand grep found 49 unbounded
`await supabase`; a mechanical check found **90** — the grep missed multi-line
`await supabase\n  .from(...)`. So `installRequestTimeouts()` in
`src/lib/supabase.ts` wraps `.from()` and `.rpc()`: every PostgREST call is
bounded by construction (15s), including code not yet written.

On timeout it **resolves** with `{ data: null, error: { code: 'TIMEOUT' } }` —
the shape callers already destructure — rather than rejecting, which would trade
silent hangs for unhandled throws. Screens may still set a tighter bound
(`listItems` uses 8s); the client is the backstop that stops "forever", not
"slow".

`auth.*` is deliberately NOT wrapped, for the revocation reason above. Those 18
call sites are listed in `scripts/unbounded-await-allowlist.json`, each with a
written reason. `npm run verify:unbounded` fails if the central bound is removed
or a new unallowlisted auth await appears; both regressions were reintroduced to
prove it bites. Pinned by `__tests__/lib/supabaseTimeout.test.ts`.

**Save paths count too.** `add-manual.tsx` had three unbounded awaits between
`setSaveState("saving")` and anything clearing it, so the button hung forever:
nothing saved, no error, nothing logged. Any await between a spinner going up
and coming down must be bounded.

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

### A second HTTP client is a second auth story (2026-08-13)

The bound-on-the-client fix above (point 4) covers `supabase` and `httpClient`.
It did not cover `src/services/collectorsClient.ts`, an undocumented third
client that built its own requests: `X-API-Key` (empty — `EXPO_PUBLIC_API_KEY`
is unset), **no `Authorization` header**, and a bare `fetch` with no timeout and
no AbortController.

Every `/portfolio/*` route takes `Depends(get_current_user_id)`, so every call
it made 401'd. Each loader in `portfolioAnalyticsStore` catches and returns
null, so the failure was silent and portfolio analytics computed an empty
portfolio for every user, forever.

**The tell is in the access log, not the code.** Same endpoint, two clients:

```
193 GET /portfolio/overview 200   <- httpClient callers
  4 GET /portfolio/items    401   <- collectorsClient, and never a 200
```

An endpoint that 200s for one caller and 401s for another is not a server
problem. Before debugging a screen that shows no data, count status codes per
path in `/opt/collectors/bake.log` — if a path has never returned 200 in
production, the caller is the bug.

**Rules:**

1. **One client.** `src/api/httpClient.ts` is it (ARCHITECTURE.md says `src/api/`
   is the API client). It owns the bearer, the single-flight 401 refresh and
   `REQUEST_TIMEOUT_MS`. Anything else calling `fetch` directly re-opens all
   three holes at once.
2. **Fix the chokepoint, not the callers.** Deleting the duplicate and
   repointing its callers looked right until tsc found `categoriesClient.ts`
   importing it as `'./collectorsClient'` — a RELATIVE path that a grep for
   `services/collectorsClient` does not match. One shared `request()` covers
   both callers and every future one. See
   [[learning_enumerate_mechanically_never_triage_by_judgment]].
3. **A silent-null loader hides the whole class.** Every loader here was
   `try { ... } catch { return null }`, which is why a 100%-failing endpoint
   produced no error, no empty state and no log for months.

**Verifying an authenticated endpoint without an app session:** mint a JWT with
`SUPABASE_JWT_SECRET` — HS256, and it needs `aud: "authenticated"` *and*
`iss: $SUPABASE_JWT_ISSUER`, or `get_current_user_id` rejects it. Then call
`http://127.0.0.1:8000` on the box with `Host: api.sparrowcollect.com`. This is
read-only; do not reset a user's password to get a token.
