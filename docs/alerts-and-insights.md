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
