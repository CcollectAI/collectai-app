# Alerts & Insights System

Data-driven portfolio insights and smart alerts for Sparrow Collect.

> **⚠️ Sections below marked _aspirational_ describe components and RPCs that were
> never deployed** (`rpc_get_alerts_feed_v1`, `rpc_get_portfolio_insights_v1`,
> `alerts_v1`, `AlertsCard`, `AlertDetailModal`). They are kept as design
> intent. **The "Actual wiring" section immediately below is the truth.** Trust it
> over the rest of this file, and over any memory of this file.
>
> **Correction 2026-08-06:** `AlertSettings` and `FEATURE_DATA_INSIGHTS_ALERTS`
> were listed above as never deployed. That is **false** — the flag is `true`
> (`src/config/featureFlags.ts:97`) and `src/screens/Settings.tsx:100` mounts
> `<AlertSettings>` today. Its endpoints exist and work
> (`GET`/`PATCH /settings/alert-preferences`, `user_settings_router.py:259`,
> `:308`) and write `user_alert_preferences` — a table with **one writer and
> zero readers**. See "Two preference stores" below.

## ⛔ `watchlist_monitor_worker` — verified working, deliberately still OFF

Dry-run 2026-07-31 (one bounded cycle, `WATCHLIST_MONITOR_BATCH=1`, never
enabled in the bake manifest). **The worker itself is fine** — it searched,
computed a median price and wrote the row back:
`last_market_price 15.02, market_hit_count 37, price_trend stable`. The alert
insert targets `alert_trigger_history`, which is exactly what the Alerts screen's
Recent tab reads, so the delivery path lines up.

**Three things must be true before it is switched on. None are today:**

1. **No item has a `target_price`.** 0 of 12. The alert condition requires
   `target_price is not None` (`watchlist_monitor_worker.py:246`), so every cycle
   would fire **zero** alerts. Enabling now is pure outbound cost.
2. **Titles are `(unnamed)`.** Legacy residue predating the 2026-06-05
   name-vs-title fix. The worker searches marketplaces for that literal string
   and persists the results — the dry run wrote **37 junk `market_hits` under
   `item_ref = "lorcana:(unnamed)"`**, prices €1.83–€417.94, from one item. Those
   rows were deleted afterwards. Enabling with these titles pollutes the price
   corpus continuously.
3. **It fans out to third-party marketplaces per item**, `BATCH_SIZE=100`
   hourly. That is the same shape that got tcgcsv.com to block us
   (see `learning_third_party_rate_bans_and_schedule_drift`). Count the outbound
   volume before, not after.

Also observed: Cardmarket now answers our Crawl4AI scrape with
**"Blocked by anti-bot protection: Cloudflare JS challenge"**.

**Enable checklist:** real watchlist titles → at least one real `target_price` →
outbound-request counting in place → then flip the manifest line and watch one
cycle.

## The watchlist screen rendered EMPTY on a cold start (fixed 2026-08-10)

Reported as "I press the watchlist item Bayou and it leads to an empty watchlist
screen". The navigation was fine — `(tabs)/index.tsx:569` pushes
`/(tabs)/wishlist` with `highlightId`, and `wishlist.tsx:73` reads it.
`check:params` is green on that handoff. The screen arrived correctly and had
nothing in it.

**`listWatchlist` ignores its `userId` argument.** `watchlistProvider.ts:19`
takes `_userId` and relies on **RLS** to scope `watchlist_items` to the caller.
So a read fired before the session hydrates is not an error and not a timeout —
it returns **zero rows**, and the screen renders its honest-looking empty state
to a member who has items.

`wishlist.tsx` destructured only `{ user }` from `useAuthContext`, never
`loading`, and its load effect ran on mount.

The provider's *timeout* path already threw rather than return `[]`, with a
comment explaining that an empty array is indistinguishable from "you have not
saved anything" — and that the watchlist is the paid feature's input, so a user
who believes it emptied has no reason to keep paying. That reasoning was right;
it just did not cover **empty because we asked too early**.

Fixed per CLAUDE.md "Loading states" §2 and §3: gate on `authLoading`, with
`GATE_MAX_WAIT_MS` (imported from `usePaginatedList`, not redeclared) as the
deadline so a wedged session cannot pin the screen.

> **Still a second implementation.** CLAUDE.md says `usePaginatedList` enforces
> this "for every caller … so this cannot be reintroduced by a new screen" — and
> this screen reintroduced it, because it hand-rolls its loader. Moving it onto
> the hook is the real fix; five mutation paths call `loadItems()` directly and
> `listWatchlist` takes no limit/offset, so it was flagged rather than done
> silently.

The same class hit **new** code the same day: the member-listings rail in
`(tabs)/marketplace.tsx` fired `GET /p2p/listings` on mount and logged its own
failure twelve times behind the login screen. Found by running the app in the
simulator, not by any checker.

## Consolidation 2026-08-06 — one alert, named "Target Hit"

Eight workers implemented four user promises, with three separate answers to
"has the thing I want hit my price?". Collapsed to one:

| Was | Now |
|---|---|
| `watchlist_monitor_worker` → `watchlist_target_met` | **alerting removed.** The worker survives as the demand-driven *supply* feed: it fetches market data for watched items and writes `market_hits`, which is what the snipe reads. That is the only path that reaches mtg/pokemon/yugioh, which `marketplace_scrape_scheduler.SKIP_CATEGORIES` excludes |
| `price_monitor_worker` → `below_threshold` | still present, still disabled, still dead twice over (no writer for `user_price_alerts`, worker commented out). **Not yet deleted** — 4 test files pin `check_threshold_alerts` |
| `alerts_worker` → `low_value` | **deleted** |
| `signal_alerts_worker` → `public.alerts` | **deleted.** Orphan table, 0 rows, no reader anywhere |
| `deal_discovery_worker` → `watchlist_snipe` | **the survivor** |

"Snipe" was never user-facing — the badge title-cased the raw column, so the
screen read "Watchlist Snipe". The label is now **"Target Hit"**
(`TRIGGER_LABELS`, app/alerts.tsx) and the push title is "Target hit". The
**stored `trigger_type` is unchanged** (`watchlist_snipe`): renaming the column
value would orphan every existing row and every server-side reference for a
cosmetic gain.

Why this one survived: it is the only implementation that requires a live,
buyable listing (`url IS NOT NULL AND is_listing IS TRUE`). The other two fire
on a computed median or a model prediction, so they can wake a user for
something that is not for sale anywhere — a notification with no action, which
is how users learn to ignore notifications.

## 🎯 `watchlist_snipe` — the join was category-only until 2026-08-04

Distinct from `watchlist_monitor_worker` above. Snipes are **Phase 2 of
`deal_discovery_worker`** (`_check_watchlist_snipes`), which *is* enabled. They
write `alert_trigger_history` with `trigger_type='watchlist_snipe'` and
`item_id='watchlist_snipe:<watchlist uuid>'`.

**What was wrong.** The join was `mh.category = w.category` and nothing else.
The docstring claimed "category + fuzzy title match"; there was no title match
in the SQL. Any listing in the category under the target fired — a €8015 target
on an MTG dual land alerted on a €0.02 common, worded "100% below your target".
Measured over a 7-day window the old predicate matched **220,826** rows.

Three conditions now define a snipe:

| Condition | Predicate | Why |
|---|---|---|
| Same item | `mh.item_ref = w.category \|\| ':' \|\| w.item_id`, else `similarity(mh.title, w.title) >= 0.55` within category | `watchlist_items.item_id` holds a **bare** canonical key (`sum-283-bayou`); `market_hits.item_ref` is **namespaced** (`mtg:sum-283-bayou`). See `learning_canonical_key_vs_item_ref_namespace` |
| Buyable | `mh.url IS NOT NULL AND mh.is_listing IS TRUE` | Most hits are price observations, not offers. Of 276k rows over 2 days only 35k had a URL; the MTG ones are Scryfall price rows. Only **ebay / crawl4ai / discogs_listing** produce URL + `is_listing` |
| Has identity | `w.title <> '(unnamed)' AND length(w.title) >= 3` | Legacy rows would otherwise match everything via the title arm |

Verified against prod in a rolled-back transaction: exact-id arm fires, title
arm fires, target-below-price suppressed, unrelated-title suppressed.
`EXPLAIN ANALYZE` 0.2 ms on the 30-minute window; both arms are index-supported
(`(item_ref, seen_at DESC)`, `(category, seen_at DESC)` per partition).

> ⚠️ **Expect silence for TCG categories.** There are currently **zero** buyable
> eBay listings for mtg/pokemon/yugioh — those categories carry Scryfall price
> rows only. The correct query therefore fires nothing for them, which is the
> point: the alerts it stops sending were unactionable by construction. Buyable
> listings do exist for warhammer, hot_toys, gunpla, anime_figures, lego,
> watches, funko and ~12 more.

**The alert must be clickable.** `trigger_value` now carries `listing_source`
alongside `provider` — `app/alerts.tsx:335` reads `listing_source` for the
button label and fell back to the literal word "Marketplace" because only
`provider` was ever written. And `app/alerts.tsx` no longer routes on
`item_id` for this trigger type: `watchlist_snipe:<uuid>` is neither an items
uuid nor a catalog key, so `itemHref` sent it to
`/catalog-item/watchlist_snipe:<uuid>`, which resolves to nothing. A snipe's
real destination is the listing; with no listing URL, no button renders.

## The marketplace feeds Target Hit — both directions (2026-08-08)

Two connections between `p2p_listing_router.py` and this feature. Neither adds
an alert type, a worker, or a `user_price_alerts` row — see
[There is now NO writer](#there-is-now-no-writer--and-that-is-deliberate-2026-08-05),
which is still true and still deliberate.

### Push: a seller drops their price

`PATCH /p2p/listings/{id}` (price only) calls `_price_change_hook`, which
UPDATEs the listing's existing buyable `market_hits` row — new `price`,
`price_eur`, and `seen_at = now()`.

That is the whole mechanism. `_check_watchlist_snipes` already selects rows with
`seen_at > now() - interval '30 minutes'` and `price_eur <= w.target_price`, so
the next cycle matches the listing against every watcher whose target the NEW
price meets, with the existing 24h-per-watchlist dedupe and plan gating applied
unchanged. **Nothing in the hook knows about users.**

| Decision | Why |
|---|---|
| UPDATE, never INSERT | `_publish_supply_hook` guards on `WHERE NOT EXISTS (provider='sparrow' AND listing_id=…)` because a second buyable row makes Target Hit surface one listing **twice**. Verified on prod that the UPDATE survives `seen_at` moving the row across a monthly partition boundary |
| A price **rise** does not refresh `seen_at` | "Listed below your target" is the promise. Waking someone because an item got *more expensive* is a notification with no action — exactly what the 2026-08-06 consolidation deleted three workers to stop. The price is still corrected so the row never advertises a stale figure |
| Awaited, not `spawn_bg` | Unlike the publish hook. A missing buyable row is a non-event; an EXISTING row advertising a price the seller no longer asks is a stale promise in both directions |

Verified end to end against prod: listed at 250 against a 200 target → no match;
dropped to 180 → matched, one row not two; aged out and raised to 195 → price
corrected, still no match; dropped to 150 → matched again.

### Pull: `GET /p2p/watchlist-matches`

The same join with **no time window and no alert** — what is buyable right now
for the items you watch. Rendered on each row of `app/(tabs)/wishlist.tsx`,
accented only when `meets_target`.

This exists because the alert is a *moment*: a member could be watching a Bayou
while another had one listed, and only a push firing at the right time would
connect them. Miss it and the two halves never meet again.

Uses the snipe's **exact-identity arm only** — `canonical_key` + `category`,
both BARE on `watchlist_items` and `marketplace_listings` (it is
`market_hits.item_ref` that is namespaced). Deliberately NOT the trigram title
fallback: that arm exists so free-text rows can still fire an alert and is tuned
at 0.55, and an alert that is occasionally loose is recoverable — a permanent row
on the watchlist screen asserting the wrong item is not.

`meets_target` is `price_eur <= target_price`, **character for character the
comparison `_check_watchlist_snipes` makes**. If the screen and the alert
disagreed about whether a listing meets a target, one of them would be calling
the user a liar about their own number.

> ⚠️ **Known gap, shared by both:** that comparison treats `target_price` as EUR,
> while the column is written in the member's display currency. A €100 target and
> a ¥100 target are stored identically. This is a real cross-currency bug and it
> belongs to the ALERT — fixing it in `watchlist-matches` alone would create the
> screen/alert disagreement the paragraph above exists to prevent. Fix both
> together or neither.

### A one-tap "watch this" control must set a target

A favourite heart was built on the marketplace grid on 2026-08-08 and removed
the same day. While it existed it called `addWatchlistItem` with **no
targetPrice**, so every row it wrote was inert — `_check_watchlist_snipes`
filters `WHERE w.target_price IS NOT NULL AND w.target_price > 0` — while the
control's own accessibility label promised "get alerted on price drops".

That is the fourth instance of this exact writer bug (see the 13-row count
below). Any future one-tap watch control must either set a target price or say
plainly that it has not.

### RESOLVED 2026-08-11 — two verbs, two stores

The heart came back, and the rule above is why it is now safe. Favouriting and
watching are separate controls writing to separate tables, so neither has to
lie about the other:

| control | writes | promises |
|---|---|---|
| ♥ heart | `public.favorites` | saved. No target, no alert, no plan gate |
| 👁 eye | `watchlist_items` via `addWatchlistItem` | a target price and a Target Hit alert |

The eye sets `targetPrice = listing.price` — the asking price — so the row
satisfies all three conditions a snipe-capable row needs (`target_price > 0`, a
slug `category`, an `item_id`). Its accessibility label says *"watch for price
drops below the asking price"*, which is now literally what it does. If the
listing has no category the control **refuses and says so**, rather than writing
the inert row that `watchlist-builder` used to produce.

The heart's label says "save", never "alert", because it does not alert.

- Table: `server/migrations/20260811_favorites.sql` (applied to prod
  2026-08-11; `favorites_one_target` CHECK, two partial unique indexes making
  the toggle idempotent, owner-only RLS)
- API: `server/app/features/favorites_router.py`
- FE: `src/api/favoritesApi.ts`, `src/hooks/useFavorites.ts` (one shared store,
  one `/favorites/ids` fetch per screen — not one per card),
  `src/components/marketplace/FavoriteWatchButtons.tsx`
- Consumer: `app/favorites.tsx`, reachable from the Market tab's control row

`app/catalog-item/[key].tsx` carried a **heart icon on its "Add to watchlist"
CTA** — the same glyph, on the same screen, meaning the other thing. It now
carries the eye. Its write was already correct and was not touched.

## What a snipe-capable watchlist row needs (writer side, 2026-08-05)

The snipe query was fixed on 2026-08-04; the **writers** were still producing
rows it could never match. Counted in prod that day — 13 rows:

| | count | consequence |
|---|---|---|
| empty `category` | **5** | fallback arm joins `mh.category = w.category` → matches nothing. All from `watchlist-builder.tsx`, which hardcoded `category: ''` and had no category field in its form |
| no `target_price` | **12** | `WHERE w.target_price IS NOT NULL AND > 0` → row is skipped entirely |
| no `item_id` | **12** | only the exact arm needs it; without it a row falls to the trigram title match |

A row can only ever fire if **all three** hold:

1. `target_price > 0`
2. `category` is a **slug** (`mtg`), matching `market_hits.category`'s vocabulary
3. `title` is real (not `(unnamed)`, ≥3 chars) — or `item_id` is set, which is
   stronger and skips the fuzzy arm

Three writer bugs fixed on 2026-08-05:

- **`watchlist-builder.tsx` sent `category: ''`.** It now has a required
  category picker (`CompactSelect`, searchable) and refuses to save without
  one. This screen is where the Alerts tab's CTA sends people, so the app's
  primary "create an alert" funnel was producing inert rows.
- **`app/(tabs)/wishlist.tsx` sent the display NAME** (`"Magic: The
  Gathering"`) because its picker is built from `CATEGORIES.map(c => c.name)`.
  `market_hits.category` holds slugs, and the server stores `payload.category`
  verbatim — no normalisation anywhere. It now converts via
  `CATEGORY_NAME_TO_SLUG`. Note `WatchlistItemCard` already assumed a slug
  (`categoryDisplayName(item.category)`), so **the display was wrong-by-luck,
  not the storage contract**. Same shape as
  `learning_canonical_key_vs_item_ref_namespace`: two ends of a join using
  different vocabularies for the same concept.
- **No target price was ever surfaced as a problem.** `WatchlistItemCard` now
  renders an explicit "No target — won't alert" chip instead of just omitting
  the target badge.

`catalog-item/[key].tsx` was already correct — it passes `itemId`, a slug
category, and `targetPrice: estPrice`, and is the source of the single row in
prod that satisfies all three conditions.

> Rows written before this fix are still inert. Prod is test data, so they were
> left alone; if that changes, they need a backfill (category ← slug, and a
> target price) or a delete.

## ⛔ THE PAID FEATURE CANNOT FIRE FOR ANY REAL USER (measured 2026-08-08)

Target Hit is the thing Pro sells. `_check_watchlist_snipes` filters:

```sql
WHERE w.target_price IS NOT NULL AND w.target_price > 0
```

Prod, today:

```
registered users        29
users with any item      6
items total             16
watchlist rows          13
watchlist WITH a target  0      <-- every row is inert
Target Hits ever         2      (both from testing, 2026-08-04/07)
paying subscribers       0
P2P listings             0
```

**Zero of thirteen watchlist rows carry a target price**, so the alert cannot
fire for a single real user, and Pro therefore has nothing to demonstrate.

The cause is not a bug in the worker — the worker is correct and verified. It is
the ADD FORM: `app/(tabs)/wishlist.tsx` requires a title and a category and
leaves the target price **optional** (`handleAdd`, the two guards at :167 and
:171). The one field that arms the feature is the only one you can skip.

`WatchlistItemCard` already renders a "No target — won't alert" chip, added
2026-08-05. Thirteen rows later, still 0 targets: **telling the user afterwards
does not work.** The field has to be required at write time, or defaulted to
something sensible (the current market estimate) and editable.

This outranks every marketplace feature. Supply, price drops, watchlist matches
and the sold-comp loop all feed an alert that is currently incapable of firing.

## THE MAP — alerts & notifications end to end (2026-08-08)

Written because the duplicate-screen problem was found by Merle asking, not by
any check. Every doc read in this codebase is scoped to the file being edited,
which is the right rule for editing and is structurally incapable of surfacing
"there are four stores for one concept". This section is the zoom-out.

### Both stores converge on ONE table

The marketplace has two supply sides and they are deliberately not separate
pipelines:

```
EXTERNAL STORE                              INTERNAL STORE
44 marketplace adapters                     Sparrow P2P listings
(ebay, cardmarket, crawl4ai, discogs…)      (member sells an item)
        |                                            |
        | marketplace_scrape_worker                  | _publish_supply_hook
        | valuation/ingest RPCs                      | _price_change_hook
        v                                            v
        +--------------->  market_hits  <------------+
                           provider='sparrow' marks ours
                                  |
                    is_listing = TRUE and url IS NOT NULL
                                  |
                                  v
              deal_discovery_worker._check_watchlist_snipes
                 join: mh.item_ref = w.category || ':' || w.item_id
                 gate: mh.price_eur <= w.target_price
                 dedupe: 24h per watchlist row + plan cap
                                  |
                 +----------------+----------------+
                 v                                 v
       alert_trigger_history                  notify_user()
       (Home AlertsCard reads this)                |
                                     +-------------+-------------+
                                     v                           v
                            notification_history            push_outbox
                            (Notifications screen)          (device push)
```

**The single most important property:** an internal listing is not a second
alert path. It writes the same `market_hits` shape with `provider='sparrow'`,
so it flows through the exact same detection, dedupe and plan gating as an eBay
row. That is why the P2P marketplace could be added without touching the alert
worker at all (spec §1), and it is why a price drop needed only a row UPDATE
(§8b) rather than a new notification type.

### Every store, and who reads it

Measured on prod 2026-08-08.

| Store | Rows | Written by | Read by | Verdict |
|---|---:|---|---|---|
| `market_hits` | 989k | both stores | valuation, snipe, catalog | ✅ the spine |
| `alert_trigger_history` | 102 | `deal_discovery_worker` | Home `AlertsCard` (`useAlertsFeed`) | ✅ live |
| `notification_history` | 11 | `notify_user` / `_persist_only` | `GET /notifications/history` → Notifications screen | ✅ live |
| `push_outbox_v1` | 0 | push worker | push worker | ✅ drains to empty |
| `user_price_alerts` | 4 | **nothing** (writer removed 2026-08-05, deliberately) | `GET /alerts/mine` | ⚠️ empty by design |
| `user_notifications` | 188 | pg_cron 30 → `rpc_emit_smart_guidance_v1` | **nothing** — 0/188 read | ❌ orphan, cron DISABLED 2026-08-08 |
| `alerts_outbox` | 31 | `produce_alerts_price_drop_30d` (job 21, **inactive**), `produce_alerts_price_spike_7d` (job 24, **inactive**) | **nothing** | ❌ orphan; **its janitor `cleanup_alerts_outbox` (job 25) is still ACTIVE**, cleaning a table nothing writes |
| `alert_delivery_queue` | 27 | `_alerts_enqueue` (DB) | **nothing** — zero repo references | ❌ orphan |
| `notifications` | 0 | nothing | nothing | ❌ ghost table |
| `notification_impressions` / `_interactions` / `_outcomes` | 0 | outcome RPCs | outcome RPCs | ⚠️ analytics, never exercised |

**Four dead alert stores** (`user_notifications`, `alerts_outbox`,
`alert_delivery_queue`, `notifications`) against **two live ones**.

### Why nothing caught this

Every gate in the repo watches PRODUCERS. None watched CONSUMERS.

| Gate | Question it asks | Blind to |
|---|---|---|
| `worker_output_registry` + silent_writer probe | "is the declared writer still writing?" | a healthy writer feeding a table nobody reads — it goes GREEN by design |
| `audit_writer_reader_drift.py` | column read/written mismatch **within `server/`** | writers that are pg_cron jobs or DB functions — not in the repo at all |
| `audit_full_chain.py` | FE call → BE handler → DB table, traced **downward** | a store with no FE entry point; there is nothing to trace from |
| `audit_rls_coverage.py` | is RLS enabled, and why is it exempt | it *asked* the right question and accepted a FALSE answer — `user_notifications` was justified as "served through /notifications", which reads a different table |

The last row is the sharpest lesson: the justification list is a good mechanism,
and a wrong entry in it is worse than no entry, because it answers the
reviewer's question and ends the investigation.

### The gate that now exists

`server/scripts/audit_orphan_stores.py` — the missing axis. It starts at the
DATABASE (`cron.job` + `pg_proc`), enumerates what is being written, and demands
a reader in `server/`, `src/` or `app/`. Where a table has an engagement column
(`read`, `read_at`, `dismissed_at`) it corroborates with VALUES: 0/188 rows ever
read is proof, not a failed grep (`learning_validate_values_not_just_structure`).

**Two phases, and that split is load-bearing.** The first version ran entirely on
EC2 and reported `market_hits`, `items` and `profiles` as orphans — tables read
on nearly every screen — because `/opt/collectors` has no `src/` or `app/`, so
every reader lookup silently returned nothing. Same shape as
`learning_ec2_deploy_path`: it ran, exited 0, and was confidently wrong.

```bash
ssh collectai '… audit_orphan_stores.py --dump-writers' > /tmp/writers.json
python3 server/scripts/audit_orphan_stores.py --writers-file /tmp/writers.json
```

Current state: **17 orphans, 10 with rows.** Known-good ones go in
`KNOWN_ORPHANS` with a reason that must be TRUE.

## The guidance subsystem is GONE too (2026-08-08)

`user_notifications` + `guidance_runs` + 30 functions + 6 views, removed. The
decision was not "is it an alert" — it is a RECOMMENDATION engine, so that rule
does not reach it. It goes for a stronger reason: **seven months of daily writes
and the engagement columns never moved once.**

```
188 rows since 2026-01-24
    0 read       0 read_at      0 dismissed
```

And its output was not worth wiring: "Best next add — BE@RBRICK", for an item
with `listings_7d: 0` and no price, the same one every day. *Buy this thing you
cannot buy and we cannot price* is worse than silence.

Deleted rather than left dormant because dormant is not free — it was carrying a
permanent expected-entry in four gates (RLS, account-deletion, schema.lock,
orphan-stores), which is how a gate stops being read. Recoverable from git and
from the database's own function history if a "what should I buy next" feature
is ever wanted; the ranking has to be rewritten either way.

### I over-deleted, and the gate caught it

The same migration dropped `notification_impressions`, `_interactions` and
`_outcomes` because they carried an FK to `user_notifications`. **Sharing a
foreign key is not being the same feature**, and I treated it as if it were.

They belong to the push-engagement loop written by
`app/features/notification_feedback_router.py`, whose three endpoints are LIVE —
`/notifications/feedback/{impression,interaction,outcome}` are in the live
OpenAPI. My "zero callers" check covered the RPCs and the frontend; it did not
cover a mounted FastAPI router writing raw SQL, and my grep for the mount point
missed it.

`preflight_router_drift` failed on TABLE_MISSING, which is what caught it. That
is a HARD gate — the next bake restart would have taken the API down. Tables
restored from the router's own INSERT statements
(`20260808_restore_notification_feedback_tables.sql`), without the FK to the
now-gone parent.

> The lesson, stated plainly: **an FK is not a feature boundary.** Two tables can
> reference each other and belong to entirely different features, and the second
> one can have a live consumer the first does not.

### Still open on that loop

All three tables have been EMPTY since 2026-04-25. The endpoints are live, the
client has `logNotificationImpression` / `Interaction` / `Outcome` in
`src/api/intelligenceApi.ts` — and **no screen calls them.** The push-quality
feedback loop is built end to end and never wired to a tap. Not fixed here.

## The dead alert subsystem is GONE (2026-08-08)

Merle's rule, and it is the right one:

> **If it is not an alert that the targeted item is available for the price the
> user wants, then it is pointless as an alert.**

That is the surviving predicate — `url IS NOT NULL AND is_listing IS TRUE AND
price_eur <= target_price` — and everything that failed it has now been removed
rather than left dormant.

### What was in there, and why it was safe to delete

```
alerts_outbox          31 rows   27 price_drop_30d + 4 price_spike_7d
                                 2025-10-22 .. 2025-11-21
alert_delivery_queue   27 rows   ALL status='delivering', delivered_at NULL
```

So 27 alerts were queued for delivery in October 2025 and **never delivered** —
the drainer had been removed with the rest of the subsystem and the queue was
left behind. That is why it looked alarming: a queue with a writer and no reader
is not the same as an unread log, and it deserved the check.

It was checked. Every one is a `price_drop_30d` / `price_spike_7d` — a **computed
price movement**, not an offer. A median that moved is not something anyone can
buy, so under the rule above none of them should ever have been sent. **No user
is owed a notification.**

Also found: `alert_delivery_queue.alert_id` is BIGINT while `public.alerts.id` is
UUID. The two could never join. The queue keyed on `alerts_outbox.id`.

### Removed

| | |
|---|---|
| cron jobs | 21 `produce_alerts_price_drop_30d`, 24 `produce_alerts_price_spike_7d`, **25 `cleanup_alerts_outbox`** — the janitor was still running daily against a table nothing had written to since November |
| tables | `alerts_outbox`, `alert_delivery_queue` |
| functions | `_alerts_enqueue`, the 2 producers, the janitor, and 7 delivery RPCs (`rpc_alert_attempt_start/finish`, `rpc_alerts_mark_delivered`, `rpc_alert_targets`, `rpc_alerts_feed_for_user`, `rpc_alerts_list`, `rpc_get_alerts_recent`) |
| view | `v_alerts_pending` — a dependent nobody had enumerated |

Three of those RPC names read like live readers, which is exactly why each was
checked rather than assumed: **zero** appear in the frontend's 16 real
`supabase.rpc()` names, and none is referenced in `server/app` or
`server/workers`.

> The view is the lesson. I enumerated the FUNCTIONS that touched the tables and
> thought that was the dependency set; `CASCADE` then reported a view I had never
> looked for. **Enumerating functions is not enumerating dependents.**

### Untouched, and verified after the drop

`alert_trigger_history` 102 rows · `notification_history` 11 · `watchlist_items` 8 ·
`/healthz` 200 · `audit:all` 15/15 · schema.lock regenerated (548 tables) and
its preflight PASS.

`user_notifications` and the 15 guidance RPCs are **not** covered by the rule
above — "Best next add" is a RECOMMENDATION, not an alert. Its cron stays
disabled and the scaffolding stays dormant, pending a decision on whether that
feature is wanted at all.

## A THIRD notification system, in the database (investigated 2026-08-08)

Flagged during the screen consolidation as "188 rows, no reader". Investigated;
it is bigger than that, and the conclusion is **do not wire it up**.

### What exists

An entire parallel notification stack lives in Postgres, not in this repo:

| | RPCs |
|---|---|
| **Writers (8)** | `rpc_emit_smart_guidance_v1`, `rpc_emit_next_best_add_v1`, `rpc_emit_progress_guidance_v1`, `rpc_emit_event_notifications_v1`, `rpc_emit_event_reminders_v1` (+`_dev`), `rpc_wishlist_compute_alerts_v1` (+`_dev`), `rpc_wishlist_compute_availability_alerts_v1` (+`_dev`) |
| **Readers (7)** | `rpc_user_inbox_v1`, `rpc_get_what_matters_now_v1` (+`_dev`), `rpc_mark_notification_read_v1`, `rpc_dismiss_notification_v1`, `rpc_compute_notification_outcomes_v1`/`v2` |

It is not a stub — there is a feed getter, a mark-read, a dismiss, and an
outcomes computation. It is a finished product.

**`pg_cron` job 30 runs it daily at 09:00 UTC:**

```sql
insert into public.guidance_runs (user_id, run_date, result)
select u.user_id, current_date, public.rpc_emit_smart_guidance_v1(u.user_id)
from public.api_active_users_v1 u
where not exists (... already ran today ...);
```

Succeeding every day — 4 users/day, unbroken.

### Nothing has ever read one

```
188 rows since 2026-01-24
    0 read
    0 read_at
    0 dismissed
```

The engagement columns are the proof. This is not "I could not find a caller" —
seven months of writes and the read/dismiss columns have never once moved.
`grep` agrees: zero callers for any of the 15 RPCs across `app/`, `src/` and
`server/`.

The RLS audit actively asserted the opposite — `user_notifications` was
justified as *"In-app notification rows served through /notifications"*. That is
false: `GET /notifications/history` reads `notification_history`. Corrected in
`server/scripts/audit_rls_coverage.py`.

### Why NOT to switch it on

The obvious move is "a finished feature is sitting there, wire the UI". Read what
it actually produces first — the newest rows, three days running, identical:

```
title    Best next add
body     BE@RBRICK 100% / 400%
why      "Missing from your collection; no recent listings yet."
signals  listings_7d: 0, listings_30d: 0, median_price_eur_30d: null
```

It recommends an item with **zero availability and no price data**, and
recommends the same one every day. That is the worst possible recommendation:
*buy this thing you cannot buy and we cannot price.* Shipping it would be worse
than the silence.

174 of the 188 rows are this one `guidance` kind. The rest are `event_reminder`
(7), `event` (3), `checklist` (2), `wishlist_price` (1), `wishlist_available`
(1) — all from 2026-01-24/25, i.e. a one-off backfill that never repeated.

### Recommendation

1. **Disable `pg_cron` job 30.** It runs an RPC per active user every day to
   produce rows nobody reads. Not urgent at 4 users; wrong at 4,000.
2. **Do not wire `rpc_user_inbox_v1`** until the recommendation logic filters on
   availability. "No recent listings" must disqualify a suggestion, not annotate
   it.
3. **Keep the RPCs.** The scaffolding is sound and the read API is complete; it
   is the ranking that is wrong. Deleting it would throw away the good half.

> Note `cron.job` also carries two INACTIVE alert producers —
> `produce_alerts_price_drop_30d` (job 21) and `produce_alerts_price_spike_7d`
> (job 24), both `active = f`. More dead alert paths, consistent with the
> 2026-08-06 consolidation that cut eight workers to one.

## Screen consolidation 2026-08-08 — four screens became two

Walked all four on the simulator. One feature was wearing FIVE names:

| route | header | empty state |
|---|---|---|
| `(tabs)/wishlist` | *(none)* | "No items in your **wishlist** yet" |
| `watchlist-builder` | COLLECTOR / **Watchlist** | "Start Your **Watchlist**" |
| `alerts` | **Alerts** | "No triggered **alerts**" + "Create an Alert" |
| `notifications` | *(blank — a bug)* | "No **notifications** yet" |

plus the stored trigger `watchlist_snipe`, labelled **Target Hit**.

The first two read the SAME table and rendered near-identical empty states. The
last two rendered the SAME EVENT — `deal_discovery_worker` writes
`alert_trigger_history` (:225) and calls `notify_user` (:248) for every Target
Hit. And "Create an Alert" on the alerts screen routed to `/watchlist-builder`,
sending the user from "alert" to "watchlist" with no explanation.

### What changed

- **`app/alerts.tsx` is DELETED.** Its Recent tab duplicated the notifications
  feed; its Rules tab was empty *by design* (see below — `user_price_alerts` has
  no writer, deliberately), so the whole screen went.
- The watchlist's **"Alerts" pill is now "Inbox"** and routes to
  `/notifications`. One inbox.
- **`watchlist-builder` was reachable ONLY from the alerts screen**, so deleting
  that screen would have orphaned it — a feature that still exists and cannot be
  reached is worse than one that was removed. It now has a **"Bulk"** pill on the
  watchlist header, which is its sole entry point.
- Vocabulary: the user-visible strings say **watchlist**. Only `en`, `nl` and
  `de` were wrong — `fr` (*liste de suivi*), `es` (*lista de seguimiento*), `ja`
  and `ko` already said watchlist.

### Two things deliberately NOT renamed

- **The `/wishlist` route.** Renaming it would break deep links for no
  user-visible gain; only the strings changed.
- **"Wishlist" as a BUILD STAGE.** `src/constants/buildStepTemplates.ts` uses it
  as step 0 of five taxonomies (`Wishlist → Purchased → Unassembled → …` for
  Warhammer, LEGO, Gunpla, Scale Models, Keycaps — docs/ARCHITECTURE.md). A
  blanket find-and-replace would have corrupted that vocabulary.

### What was checked before deleting a screen

Counting prod first is what stopped this going wrong — the merge as originally
proposed would have deleted the WORKING screen:

```
alert_trigger_history   102 rows   <- the Alerts screen read this
notification_history     11 rows   <- the Notifications screen reads this
user_notifications      188 rows   <- NO READER FOUND
notifications             0 rows   <- ghost table
```

Four tables for one concept. Decision (Merle, 2026-08-08): **merge anyway, do
not backfill.** 100 of the 102 rows are `low_value` / `weekly_digest` /
`value_change` from workers deleted in the 2026-05-04 pre-launch cut — a backlog
of dead notifications. Only 2 were real Target Hits.

Also verified before deleting: **zero** stored `deep_link` values point at
`/alerts`, and no server code emits one, so no push or shared link can land on
the removed route.

> ⚠️ **Still open:** `user_notifications` holds 188 rows across 5 users, still
> being written today, with no reader found. That is a third notification store
> and it was NOT resolved here.

## Actual wiring (verified E2E against prod 2026-07-30)

There are **two different things** here, and crossing them has broken this
feature twice:

| Concept | Meaning | Endpoint | Table | FE reader |
|---------|---------|----------|-------|-----------|
| **Rule** | A standing condition the user configured | `GET /alerts/mine` | `user_price_alerts` | `dataProvider.listAlertRules` → `AlertRule` |
| **Trigger** | A record of a rule having fired | `GET /alerts/trigger-history` | `alert_trigger_history` | `dataProvider.listAlertsFeed` → `AlertFeedItem` |

`app/alerts.tsx` has a tab for each. The **Rules** tab must use `listAlertRules`;
the **Recent** tab and the Home-screen feed (`useAlertsFeed`) use
`listAlertsFeed`. `AlertRule` and `AlertFeedItem` are separate types precisely so
the compiler stops them being swapped.

### There is now NO writer — and that is deliberate (2026-08-05)

`app/(tabs)/wishlist.tsx` used to auto-create a `below_threshold` rule from a
watchlist **target price** (two call sites: add-item and edit-target). **Both
were removed.** The rule could never fire:
`price_monitor_worker.check_threshold_alerts` selects
`WHERE ... AND a.item_id IS NOT NULL` (`:84`), and a watchlist row is not an
`items` uuid, so the wishlist could not supply one. Counted against prod:

```
user_price_alerts:     4 rows, all below_threshold, all item_id NULL
alert_trigger_history: 0 below_threshold rows, ever
```

The toast said *"Price alert created — we'll notify you when the price drops
below €X"*. Nothing was watching. It now says *"Target set — we'll alert you if
it's listed below €X"*, which is what actually happens: the target is read
directly by `deal_discovery_worker._check_watchlist_snipes`, which needs **no
rule row at all**.

Consequence: `user_price_alerts` has no writer in the app, so the **Rules tab is
empty by design**. Do not "fix" it by re-adding the POST. If standing rules are
ever wanted, the honest source is the watchlist targets themselves.

**Do not** make `check_threshold_alerts` fall back to matching on `category`
when `item_id` is NULL. That is precisely the over-broad predicate that was cut
out of the snipe query above (220,826 matching rows over 7 days, a €0.02 common
alerting against a €8015 target).

This is the third instance of the same bug class in this one feature — see
[Two bugs this cost](#two-bugs-this-cost), now three.

### Legal field values — server, DB, and client must all agree

`PriceAlertCreate` (`alerts_feature_router.py:55`) and the
`user_price_alerts_direction_check` / `_trigger_type_check` CHECK constraints
both allow exactly:

- `direction`: `'up' | 'down'` (or NULL)
- `trigger_type`: `'below_threshold' | 'category_trend' | 'high_prediction'`

These are typed as literal unions in `src/api/alertsApi.ts`
(`AlertDirection`, `AlertTriggerType`). **Do not widen them back to `string`.**
They were `string`, and the wishlist sent `direction: 'below'` — a 422 on every
call, caught and only logged, so no alert was ever created and the user saw no
error. See [Two bugs this cost](#two-bugs-this-cost).

### Plan limit (now unreachable from the app)

Free = **1 price alert per week** (`PLAN_LIMIT_ALERTS`, HTTP **403**) on
`POST /alerts/mine`. The endpoint and the cap still exist, but **no client
calls it** since the wishlist writers were removed, so no user can hit this
limit today. Kept documented because the server-side enforcement is still
live — if a rule-creation UI is ever built, it must handle the 403 and must
not report it as success.

### Three bugs this cost

Found 2026-07-30 by seeding a real rule and looking at the screen (1, 2) and
2026-08-05 by counting prod (3):

1. **No wishlist alert had ever been created.** `direction: 'below'` → 422 on
   both call sites, swallowed by the catch. Prod contained zero rows with a
   `'below'` direction because the constraint would not accept one.
2. **The Rules tab could never show a rule.** It called `listAlertsFeed`, so it
   duplicated the Recent tab, showed "No alert rules yet" regardless, and its
   swipe-to-delete passed an `alert_trigger_history` id to
   `DELETE /alerts/mine/{alert_id}` — a 404 every time. `collectorsApi.getMyAlerts`
   (the correct reader) already existed, exported, with **zero callers**.

3. **Even after 1 and 2 were fixed, no rule could ever fire.** The writer sent
   no `item_id`; the worker requires one. Found 2026-08-05 by counting prod
   rather than reading the code — 4 rules, 0 triggers. Both call sites are now
   removed (see [There is now NO writer](#there-is-now-no-writer--and-that-is-deliberate-2026-08-05)).

All three are the house bug class: a reader and a writer that never meet,
failing silently to empty. None is visible on an empty account, and no test
caught any of them — the writer's 422, the reader's wrong endpoint and the
`item_id IS NOT NULL` filter each produced a plausible-looking empty list.

For completeness: `price_monitor_worker` is **also commented out of the bake
manifest** (`bake_orchestrator.py:107`), so the rule path is dead twice over —
the worker that would skip those rules is not running in the first place.

## Overview

The insights and alerts system helps users understand how their collections change over time and notifies them about important events like price drops, new listings, and milestones.

## Features

### Portfolio Insights

Displays key metrics about your collection:

- **Total Value**: Current estimated value of all items
- **Value Change**: Percentage change over selected period (7d/30d/90d)
- **Top Gainers**: Items with highest value increase
- **Top Losers**: Items with highest value decrease
- **Watchlist Summary**: Items below target price, new listings

### Smart Alerts

Seven types of alerts, all routed through `app/lib/notify.py` for
preference-aware, frequency-capped push delivery. **The "Enabled" column is the
one that matters** — this table described capability, and five of the seven
workers are commented out of `bake_orchestrator.py` (verified 2026-08-06):

| Alert Type | Trigger | Worker | Enabled? |
|------------|---------|--------|----------|
| Price Threshold | Item drops below user threshold | price_monitor_worker | ❌ `:107` |
| Price Anomaly | Z-score > 2.0 (spike/drop) | price_monitor_worker | ❌ `:107` |
| Set Completion | User owns >50% of a set | price_monitor_worker | ❌ `:107` |
| Watchlist Target Met | Market price ≤ target price | watchlist_monitor_worker | ❌ `:113`, deliberately — see top of file |
| Deal Found / snipe | Mandate match, or watchlist target met on a buyable listing | deal_discovery_worker | ✅ `:93` |
| Auction Ending | Watched auction ending in <15min | auction_alert_worker | ❌ `:117` |
| Low Value | Item valued below 10 EUR | alerts_worker | ❌ `:109` |
| Value Change | Portfolio >5% or item >15% | value_change_worker | ✅ `:95` |
| Weekly Digest | Weekly summary | insights_digest_worker | ❌ `:186` |

What that means for the Alerts screen, counted in prod 2026-08-06:

```
low_value       58   2026-04-19 .. 2026-04-22
weekly_digest   30   2026-04-20 .. 2026-04-22
value_change    12   2026-04-20 .. 2026-04-22
watchlist_snipe  1   2026-08-04 .. 2026-08-04
```

Everything except the snipe is a **backlog from before the 2026-05-04
pre-launch manifest cut**. The screen looks populated; nothing has been added
to it in 3½ months except one snipe. Note `value_change_worker` IS enabled and
runs clean (10 ok runs in 3 days, `worker_runs`) but has emitted nothing since
April — plausible on test data, since it needs a >5% portfolio or >15% item
move, but unverified.

### Notification Preferences — UI shipped 2026-07-31

`src/components/settings/NotificationPreferencesSection.tsx`, mounted in
`src/screens/Settings.tsx` directly under Privacy. Eight switches, one per
server key, reading `GET /notifications/preferences` and writing a **single-key**
`PUT` per toggle.

Before this the API worked perfectly and had **zero screen callers** — a user
had no way to turn any push category off. That was tolerable only because every
sending worker is disabled; it stops being tolerable the moment one is
re-enabled, and it is the kind of thing App Store review looks for.

Verified against prod: a single-key `PUT {"price_alerts": false}` returns 200
and **leaves the other seven untouched**, so toggles cannot clobber each other.

Two deliberate details:

- Loaded prefs are **merged over defaults**, so a key the server adds before the
  client knows about it reads as `true` rather than `false` — showing a category
  as off while pushes still arrive would be worse than showing it on.
- It goes through `collectorsApi`, which **throws on a non-2xx**, so a failed
  save rolls the switch back and toasts. The raw-`fetch` settings writes this
  replaced did not, and diverged silently (see ARCHITECTURE.md).

Do not invent keys here. The set is fixed by `NotificationPreferencesUpdate`
(`notification_router.py:236`); an unknown key is silently dropped by Pydantic,
which is exactly how a toggle becomes a no-op.

### Two preference stores — one is read, one is not (found 2026-08-06)

Settings currently renders **two** notification-preference UIs, one below the
other, controlling overlapping concepts:

| Section | Endpoint | Table | Read at delivery time? |
|---|---|---|---|
| `NotificationPreferencesSection` | `/notifications/preferences` | `user_settings.notification_preferences` | **Yes** — `notify.py::_get_user_prefs` |
| `AlertSettings` (`FEATURE_DATA_INSIGHTS_ALERTS`, `true`) | `/settings/alert-preferences` | `user_alert_preferences` | **No** |

`grep -rn user_alert_preferences server` returns the PATCH writer, the GET
reader that serves the same screen back to itself, and one entry in
`account_router.py`'s deletion list. **No worker and no notify path consults
it.** Prod has 1 row, so it has been used.

That makes `AlertSettings` a settings panel whose switches do nothing:
"Price Drops", "Drop threshold" (5–25%), "Price Increases", "Increase
threshold", "New Listings", milestones, and a frequency selector offering
Immediate / Daily Digest / Weekly Digest. None of those knobs is consulted by
anything that sends a notification, and several describe alert types whose
workers are disabled anyway.

Same class as everything else in this file — a writer with no reader — but
this one is **user-facing and promises control it does not have**. Options, in
order of honesty: flip `FEATURE_DATA_INSIGHTS_ALERTS` to `false` (one line,
removes the panel), delete the component and its endpoints, or wire
`notify.py` to actually consult `user_alert_preferences`. Do not leave it
mounted as-is.

### Frequency Capping

Push notifications are capped per tier to prevent notification fatigue:

| Tier | Daily Cap |
|------|-----------|
| Free | **3** pushes/day |
| Pro | 15 pushes/day |
| Premium | 30 pushes/day |

Free was documented as 5 until 2026-08-06; the code has always said 3
(`FREE_DAILY_CAP`, `app/lib/notify.py:26`). The code is the truth.

Urgent alerts bypass the cap (`notify.py:293`, `if not urgent`) but still
respect preferences. Only two callers pass `urgent=True` —
`watchlist_monitor_worker:290` and `auction_alert_worker:177` — **and both of
those workers are commented out of the bake manifest**, so in practice nothing
currently bypasses the cap.

## Usage

### Fetching Insights

```typescript
import { usePortfolioInsights } from '@/hooks/usePortfolioInsights';

function MyComponent() {
  const { insights, isLoading, error, refetch } = usePortfolioInsights({
    period: '7d',
  });

  if (isLoading) return <LoadingSpinner />;
  if (!insights) return null;

  return <InsightsCard insights={insights} />;
}
```

### Fetching Alerts

```typescript
import { useAlertsFeed } from '@/hooks/useAlertsFeed';

function MyComponent() {
  const { alerts, unreadCount, markAsRead, markAllAsRead } = useAlertsFeed({
    limit: 10,
    unreadOnly: false,
  });

  return (
    <AlertsCard
      alerts={alerts}
      onAlertPress={(alert) => {
        markAsRead(alert.id);
        showAlertDetail(alert);
      }}
    />
  );
}
```

## Components (aspirational — none of these are mounted; see "Actual wiring" above)

### InsightsCard

Displays portfolio insights summary.

```tsx
<InsightsCard
  insights={insights}
  onViewDetails={() => navigation.navigate('InsightsDetail')}
/>
```

### AlertsCard

Lists pending alerts.

```tsx
<AlertsCard
  alerts={alerts}
  onAlertPress={(alert) => setSelectedAlert(alert)}
  onViewAll={() => navigation.navigate('AllAlerts')}
/>
```

### AlertDetailModal

Shows full alert details with actions.

```tsx
<AlertDetailModal
  alert={selectedAlert}
  visible={!!selectedAlert}
  onClose={() => setSelectedAlert(null)}
  onViewItem={(itemId) => navigation.navigate('ItemDetail', { itemId })}
  onUpdateThreshold={(alert) => showThresholdEditor(alert)}
/>
```

### AlertSettings

Settings UI for alert preferences.

```tsx
<AlertSettings
  preferences={alertPreferences}
  onUpdate={(prefs) => saveAlertPreferences(prefs)}
/>
```

## Backend RPCs (aspirational — never deployed; see "Actual wiring" above)

### rpc_get_portfolio_insights_v1

Returns portfolio analytics.

**Parameters:**
- `period`: '7d' | '30d' | '90d'

**Returns:**
```typescript
{
  totalValue: number;
  valueChange: number;
  percentChange: number;
  period: string;
  topGainers: ItemMover[];
  topLosers: ItemMover[];
  watchlistSummary: WatchlistSummary;
  calculatedAt: string;
}
```

### rpc_get_alerts_feed_v1

Returns pending alerts.

**Parameters:**
- `limit`: number
- `unread_only`: boolean

**Returns:**
```typescript
Alert[]
```

## Alert Thresholds

Users can configure alert thresholds in Settings → Alerts:

- **Price Drop**: 5%, 10%, 15%, 20%, 25%
- **Price Increase**: 5%, 10%, 15%, 20%, 25%

## Notification Frequency

Three frequency options:

- **Immediate**: Push notification when alert triggers
- **Daily Digest**: One notification per day with all alerts
- **Weekly Digest**: One notification per week with all alerts

## Calm UX Guidelines

1. **One card per day**: The guidance system shows at most one insight card per day
2. **Consolidate alerts**: Multiple alerts in a short period become a single digest
3. **Respect preferences**: Always check user's frequency and enabled settings
4. **Non-intrusive**: Alerts should inform, not annoy

## Feature Flag (aspirational — FEATURE_DATA_INSIGHTS_ALERTS is not wired)

Gate behind `FEATURE_DATA_INSIGHTS_ALERTS`:

```typescript
if (featureFlags.FEATURE_DATA_INSIGHTS_ALERTS) {
  return <InsightsCard insights={insights} />;
}
return null;
```

## Database Tables (aspirational — the live tables are user_price_alerts + alert_trigger_history)

- `alerts_v1`: Stores triggered alerts
- `alert_preferences_v1`: User alert settings
- `price_predictions_v2`: Value predictions for change calculations
- `market_comps`: Market comparables for listings

## Testing

Run tests:

```bash
npm test src/hooks/usePortfolioInsights
npm test src/hooks/useAlertsFeed
npm test src/components/home/InsightsCard
```

---

# Privacy toggles (Settings → Privacy)

> Enforcement landed 2026-08-04. Before that, `user_privacy_settings` had
> **zero readers** — see below. Gate: `server/scripts/verify_privacy_enforcement.py`.

## Where enforcement lives — and why not in React

| Toggle | Default | Enforced by | Effect when off |
|---|---|---|---|
| Show collection value | `true` | `user_public_profile_v1` / `user_public_profiles` | `collection_value_eur` returns NULL |
| Show item count | `true` | same two views | `collection_count` returns NULL |
| Allow discovery | `true` | `user_public_profiles` WHERE clause | Excluded from `searchUsers` |
| Show online status | `false` | `rpc_get_presence_v1` + `rpc_get_batch_presence_v1` | RPC returns no row |

The app reads these views **directly over PostgREST**, and the presence RPCs are
`SECURITY DEFINER` (they bypass RLS by design so one user can see another's
dot). A check in a React component would therefore be advisory only — anyone
holding an anon key can call the RPC. The gate has to be in the DB.

**You are always exempt from your own gates**: `p.id = auth.uid()` short-circuits
the discovery and presence predicates, so opting out never hides you from your
own search results or your own presence dot.

## Two traps, both load-bearing

1. **`security_invoker` must stay OFF on both views.** `user_privacy_settings`
   has owner-only SELECT policies. A *non*-invoker view evaluates that RLS as
   the view owner and can read every row; an invoker view reads nothing for
   other users, `COALESCE` then supplies the permissive default, and **every
   gate silently opens** while still looking correct. Pinned by the verify
   script.
2. **`user_public_profiles` must stay auto-updatable.**
   `account_router._do_account_delete` issues `DELETE FROM user_public_profiles`
   and only catches `UndefinedTableError`. Adding a JOIN or a target-list
   aggregate makes the view read-only and turns **account deletion into a 500**.
   That is why the stats are scalar subqueries in the SELECT list rather than a
   `LEFT JOIN` — one table in the FROM keeps the view updatable. Also pinned.

## Why no test caught the original bug

Every existing check asked a **structural** question — "does the toggle save?"
It did save; the write path had optimistic update, rollback and a toast, and was
never broken. The question that mattered was about **values**: with the toggle
off, is the data actually hidden? Nothing asked it, and `show_online_status`
(default `false`) failed *open* for months — presence rendered regardless.

`verify_privacy_enforcement.py` asks the value question against the live DB in a
rolled-back transaction. Note it **stratifies**: presence is tested against a
user that actually has a `user_presence` row, because any other user returns
zero rows whether the gate works or not — a valid-looking empty result that
proves nothing (`learning_validate_values_not_just_structure`).

## Where profiles are actually reachable

`/users/[userId]`, and the app has exactly **one** route to it: the collector
search inside `CategoryHeaderCard` → `CategoryCollectorSearch` → `searchUsers`.
It is registered in `app/_layout.tsx` but nothing else links to a profile — not
items, not events, not the activity feed. Discovery being gated therefore gates
essentially all third-party profile access today.

## Account deletion — NOT a gap

`user_privacy_settings.user_id` is `REFERENCES auth.users(id) ON DELETE CASCADE`,
and `account_router` calls `supabase_admin.auth.admin.delete_user(user_id)`, so
the row goes with the auth user (bucket 1 of the three the audit recognises).
`audit_account_deletion.py` reports **0 uncovered tables**. The
`user_privacy_settings_v1` entry in `_ALLOWED_TABLES` refers to a separate,
empty legacy table and is harmless.

The audit does warn that `item_images` is listed but no longer exists. Left in
deliberately: the delete loop catches `UndefinedTableError`, so a stale entry
costs nothing, whereas removing it means a future re-created `item_images` would
be silently missed. A stale entry fails safe; a missing one does not.

## New notification category: `account` (2026-08-09)

`notify.py`'s `_FEED_TYPE_BY_CATEGORY` gained `"account": "system"`.

**Why it needed an entry at all.** An unmapped category is not an error — it
passes through, logs a warning, and renders the generic fallback icon. That is
the silent-degradation shape this file exists to document, so the mapping is
added at the same time as the first caller rather than after someone notices an
ugly icon.

Its first (and currently only) sender is `_dac7_accrue` in
`p2p_offers_router.py`, which warns a seller once when they pass the DAC7
reporting threshold — see `docs/P2P_MARKETPLACE_SPEC.md` §9d. Two properties of
that call are deliberate and worth not "cleaning up":

* **`urgent=True`**, so the daily frequency cap cannot suppress it. A compliance
  notice is not a discovery alert and must not compete with one for a slot.
* **It survives a muted category.** `prefs.get(category, True)` defaults to
  allowed, and since 2026-08-08 the muted branch calls `_persist_only` before
  returning — so even a member who has turned the category off still gets the
  durable in-app record. That matters here more than anywhere else: this is the
  notice we would be held to having sent.

**Related fix, same pass.** Two `deep_link` values were written in scheme form
(`sparrow://events/{id}`, and my own first draft of the DAC7 link). The
notifications screen dispatches non-http links via `router.push(deep_link)`,
which needs an expo-router **path** — a `sparrow://` URL resolves to nothing.
Both were corrected to path form (`/events/{id}`, `/legal/marketplace-terms`).
The pre-existing one had been shipped in `billing_router` and is exactly the
dead-button class: a paid-tier sponsored-event push whose tap went nowhere.

## The push tap went nowhere — two payloads, four key names (2026-08-13)

Target Hit fired correctly and pushed correctly, and **tapping the notification
did nothing at all**: the app opened wherever it already was. For the one alert
whose entire value is reaching a live listing before it sells, that is the
notification-with-no-action the 2026-08-06 consolidation deleted three workers
to stop.

The cause is that one alert has **two** payloads, and they use different names
for the same thing:

| Payload | Written by | Keys | Read by |
|---|---|---|---|
| `alert_trigger_history.trigger_value` | `deal_discovery_worker` | `listing_url`, `affiliate_url` | the notifications SCREEN |
| Expo push `data` | same worker | `url` | `usePushNotifications` tap handler |

The tap handler read `affiliate_url` / `listing_url` — the *first* payload's
names — against the *second* payload. Nothing matched, so `directUrl` was
undefined and the tap fell through every branch to the bottom of the chain.

**And `deep_link` never reached the device.** `notify_user(deep_link=…)` looked
like the answer and every reader assumed it was: `send_push_to_user` persisted
it to `notification_history.deep_link` (which is what makes the in-app rows
tappable) and merged only `notification_id` into the outgoing `data`. The
destination existed at every layer except the one the phone receives.

**Fixed in two places, chokepoint first:**

1. `app/push.py` merges `deep_link` into the outgoing `data` when a caller set
   one and did not already put a destination there. Every worker that computes
   a destination now gets a working tap — `catalog_learning_worker`,
   `p2p_offers_router`, `billing_router` all pass `deep_link` and were equally
   dead.
2. `usePushNotifications` resolves the first non-empty of `affiliate_url`,
   `listing_url`, `deep_link`, `url`, so pushes already in flight work and no
   future sender has to guess the client's preferred spelling.

Routing after that is unchanged and already correct: `inAppListingHref` sends
our OWN listings to `/listing/[id]` in-app, and anything else goes to the
browser through the `http:`/`https:` scheme allowlist — affiliate-tagged, so
the click is attributable.

**The lesson is the house one.** A writer and a reader named the same value
differently and nothing failed loudly — no error, no log, just a notification
that did nothing when tapped. Before trusting a push destination, check what
arrives on the DEVICE, not what the worker computed.
