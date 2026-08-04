# Alerts & Insights System

Data-driven portfolio insights and smart alerts for Sparrow Collect.

> **⚠️ Sections below marked _aspirational_ describe components and RPCs that were
> never deployed** (`rpc_get_alerts_feed_v1`, `rpc_get_portfolio_insights_v1`,
> `alerts_v1`, `alert_preferences_v1`, `AlertsCard`, `AlertDetailModal`,
> `AlertSettings`, `FEATURE_DATA_INSIGHTS_ALERTS`). They are kept as design
> intent. **The "Actual wiring" section immediately below is the truth.** Trust it
> over the rest of this file, and over any memory of this file.

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

### The only writer

`app/(tabs)/wishlist.tsx` — setting a watchlist **target price** auto-creates a
`below_threshold` rule (two call sites: add-item and edit-target). There is no
other way to create an alert in the app; the Alerts screen's "Create an Alert"
CTA routes to `/watchlist-builder`.

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

### Plan limit

Free = **1 price alert per week** (`PLAN_LIMIT_ALERTS`, HTTP **403**), so a
second target price legitimately fails. Both wishlist call sites surface the
server's message as an `info` toast; the watchlist target itself is already
saved by then. Do not report this as a success — one site used to show
"Target price saved" as a `success` toast on alert failure.

### Two bugs this cost

Found 2026-07-30 by seeding a real rule and looking at the screen:

1. **No wishlist alert had ever been created.** `direction: 'below'` → 422 on
   both call sites, swallowed by the catch. Prod contained zero rows with a
   `'below'` direction because the constraint would not accept one.
2. **The Rules tab could never show a rule.** It called `listAlertsFeed`, so it
   duplicated the Recent tab, showed "No alert rules yet" regardless, and its
   swipe-to-delete passed an `alert_trigger_history` id to
   `DELETE /alerts/mine/{alert_id}` — a 404 every time. `collectorsApi.getMyAlerts`
   (the correct reader) already existed, exported, with **zero callers**.

Both are the house bug class: a reader and a writer that never meet, failing
silently to empty. Neither is visible on an empty account, and no test caught
either — the writer's 422 and the reader's wrong endpoint both produced a
plausible-looking empty list.

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

Seven types of alerts, all routed through `app/lib/notify.py` for preference-aware, frequency-capped push delivery:

| Alert Type | Trigger | Worker | Push |
|------------|---------|--------|------|
| Price Threshold | Item drops below user threshold | price_monitor_worker | Yes |
| Price Anomaly | Z-score > 2.0 (spike/drop) | price_monitor_worker | Yes |
| Set Completion | User owns >50% of a set | price_monitor_worker | Yes |
| Watchlist Target Met | Market price ≤ target price | watchlist_monitor_worker | Yes |
| Deal Found | Mandate match passes policy engine | deal_discovery_worker | Yes |
| Auction Ending | Watched auction ending in <15min | auction_alert_worker | Yes (urgent) |
| Low Value | Item valued below 10 EUR | alerts_worker | Yes |

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

### Frequency Capping

Push notifications are capped per tier to prevent notification fatigue:

| Tier | Daily Cap |
|------|-----------|
| Free | 5 pushes/day |
| Pro | 15 pushes/day |
| Premium | 30 pushes/day |

Urgent alerts (watchlist target met, auction ending) bypass frequency caps but still respect user preferences.

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
