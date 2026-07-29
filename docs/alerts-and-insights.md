# Alerts & Insights System

Data-driven portfolio insights and smart alerts for Sparrow Collect.

> **⚠️ Sections below marked _aspirational_ describe components and RPCs that were
> never deployed** (`rpc_get_alerts_feed_v1`, `rpc_get_portfolio_insights_v1`,
> `alerts_v1`, `alert_preferences_v1`, `AlertsCard`, `AlertDetailModal`,
> `AlertSettings`, `FEATURE_DATA_INSIGHTS_ALERTS`). They are kept as design
> intent. **The "Actual wiring" section immediately below is the truth.** Trust it
> over the rest of this file, and over any memory of this file.

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

### Notification Preferences — API only, **no UI yet** (verified 2026-07-30)

`GET`/`PUT /notifications/preferences` both work: all 8 keys round-trip and
persist (tested against prod). What does **not** exist is a screen to change
them — `getNotificationPreferences` / `updateNotificationPreferences` are
exported on `collectorsApi` with **zero screen callers**, `app/notifications.tsx`
is history-only (no toggles), and neither `app/settings.tsx` nor
`src/screens/Settings.tsx` has a notification section.

That is consistent with the pre-launch posture rather than a defect: every
worker that would *send* these is commented out of the bake manifest under
`── DISABLED — post-launch features (no users yet) ──`
(`bake_orchestrator.py:90`) — `alerts_worker`, `price_monitor`,
`watchlist_monitor_worker`, `scarcity_monitor_worker`, `auction_alert_worker`,
`signal_alerts_worker`. There is nothing to opt out of yet, and `chat_messages`
/ `connection_requests` gate features `COMMUNITY_GATED` hides anyway.

**When the senders are re-enabled, the toggle UI must land in the same wave** —
shipping notifications with no way to turn them off is the one part of this that
would be a real defect. The server side is ready; it needs a screen only.

The 8 keys (enforced by `app/lib/notify.py`, defaults all `true`):

| Preference Key | Controls |
|---------------|----------|
| `price_alerts` | Threshold, anomaly, set completion, watchlist target, auction ending |
| `deal_alerts` | Deal discovery notifications |
| `value_changes` | Portfolio value change summaries |
| `item_value_changes` | Individual item value changes |
| `weekly_digest` | Weekly collection digest |
| `chat_messages` | Chat/DM notifications |
| `connection_requests` | Social connection requests |
| `event_announcements` | Event announcements |

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
