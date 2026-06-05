# FE Intelligence Wiring Spec

The backend has 6 endpoints sitting dormant — they exist, they're tested, they're mounted at root + `/v1`, but no React Native client code calls them. Wiring them turns ~5 demand-loop signals from "captured nothing" to "captured everything" on day-one of users.

This doc is the implementation spec: which RN file to edit, what payload to send, what user event triggers each call. Every endpoint already has rate limiting (60/min per user) so client-side debouncing only matters for hot-paths (push impressions on a busy app).

All paths assume the existing API base URL helper (`src/api/apiBase.ts` or wherever the app sets `EXPO_PUBLIC_API_URL`) and the existing auth helper that injects the JWT.

---

## 1. Push notification feedback (3 endpoints)

**Backend**: `POST /notifications/feedback/{impression,interaction,outcome}` defined in `server/app/features/notification_feedback_router.py`.

**Tables it writes**: `notification_impressions`, `notification_interactions`, `notification_outcomes` (currently 0 rows each).

### 1a. Impression — push DELIVERED to device

**RN file**: `src/hooks/usePushNotifications.ts`

**Trigger**: inside the existing `Notifications.addNotificationReceivedListener` callback (already exists for displaying the push). The `notification.request.identifier` IS the `notification_id` we want to send back — the backend stores it when sending via `push_outbox_v1`.

**Implementation**:
```ts
// inside the addNotificationReceivedListener callback:
const notificationId = notification.request.identifier; // UUID string from push_outbox_v1
// Fire-and-forget POST. Don't await — push UI must render immediately.
postFeedback("impression", { notification_id: notificationId, client_context: {
  appState: AppState.currentState,           // 'active'|'background'|'inactive'
  platform: Platform.OS,                     // 'ios'|'android'
  receivedAt: new Date().toISOString(),
} });
```

**Helper to add** (single file: `src/api/notificationFeedbackApi.ts`):
```ts
export async function postFeedback(
  kind: "impression" | "interaction" | "outcome",
  body: object,
): Promise<void> {
  try {
    await fetch(`${API_URL}/notifications/feedback/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${jwt}` },
      body: JSON.stringify(body),
    });
  } catch {
    // Best-effort — never throw from the push pipeline
  }
}
```

### 1b. Interaction — push TAPPED / dismissed / etc

**RN file**: `src/hooks/usePushNotifications.ts`

**Trigger**: `Notifications.addNotificationResponseReceivedListener` callback (already exists for deep-link routing).

**Payload**:
```ts
const notificationId = response.notification.request.identifier;
const kind =
  response.actionIdentifier === Notifications.DEFAULT_ACTION_IDENTIFIER ? "open"
  : response.actionIdentifier === Notifications.DISMISS_ACTION_IDENTIFIER ? "dismiss"
  : "action";
postFeedback("interaction", {
  notification_id: notificationId,
  kind,
  meta: { action_id: response.actionIdentifier },
});
```

### 1c. Outcome — downstream user action AFTER a push

**RN file**: NEW small file `src/lib/notificationOutcomeTracker.ts`. Uses an in-memory map of `{notification_id: tappedAt}` populated when 1b fires.

**Trigger**: across the app, when the user takes a high-signal action (item added, watchlist add, ticket purchase, deal offer made). Inspect the tracker for any tapped notification within the last 30 min and emit an outcome.

**Skeleton**:
```ts
// notificationOutcomeTracker.ts
const recentTaps = new Map<string, number>(); // notification_id → tappedAt epoch ms

export function trackTap(notificationId: string) {
  recentTaps.set(notificationId, Date.now());
  // GC: drop entries > 30 min
  for (const [id, t] of recentTaps) if (Date.now() - t > 30 * 60_000) recentTaps.delete(id);
}

export function emitOutcome(actionType: "bought" | "followed" | "sold" | "added" | "ignored" | "other",
                            actionRef?: object) {
  if (recentTaps.size === 0) return;
  // Fire one outcome per tapped notification (cap at 5 to avoid burst)
  const entries = Array.from(recentTaps.entries()).slice(0, 5);
  for (const [notificationId, tappedAt] of entries) {
    postFeedback("outcome", {
      notification_id: notificationId,
      outcome: actionType === "ignored" ? "ignored" : "converted",
      latency_seconds: Math.floor((Date.now() - tappedAt) / 1000),
      action_type: actionType,
      action_ref: actionRef,
    });
    recentTaps.delete(notificationId);
  }
}
```

**Call sites**:
- `src/hooks/usePushNotifications.ts` interaction callback → `trackTap(notificationId)`
- `src/data/SupabaseDataProvider.ts` (or wherever item add succeeds) → `emitOutcome("added", { item_id })`
- `src/api/marketplaceApi.ts` (deal offer success) → `emitOutcome("bought", { offer_id })`
- Watchlist add → `emitOutcome("followed", { item_id })`

---

## 2. Affiliate-click (1 endpoint)

**Backend**: `POST /marketplace/affiliate-click` in `server/app/routes/affiliate_links_router.py`.

**Trigger**: every time the user taps an external marketplace link. The current FE has affiliate URLs in 7+ components but no tracking when they're opened.

**RN file to add the call to**: `src/utils/affiliateHelpers.ts` — wrap the existing helper that calls `Linking.openURL`. ALL the components that use this helper (ItemShopSection, MarketplacePickerSheet, MarketplaceResultCard, BarcodeResultCard, SearchResultQuickView, MarketplacePricesSection, the catalog museum screen `app/catalog-item/[key].tsx`) get the tracking automatically. (ExternalMarketplacesSection was removed from the category page in the 2026-06-05 museum redesign — the museum's "Where to buy" rail is the affiliate surface there now.)

**Implementation**:
```ts
// inside affiliateHelpers.ts, alongside the existing openAffiliate()
export async function trackAffiliateClick(args: {
  source: string;          // 'ebay'|'tcgplayer'|'cardmarket'|'mercari'|'discogs'|'stockx'|...
  query?: string;
  item_key?: string;
  category?: string;
}) {
  try {
    await fetch(`${API_URL}/marketplace/affiliate-click`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${jwt}` },
      body: JSON.stringify(args),
    });
  } catch { /* swallow */ }
}

// modify existing openAffiliate:
export function openAffiliate(url: string, source: string, ctx?: {query?: string; item_key?: string; category?: string}) {
  trackAffiliateClick({ source, ...ctx });   // fire-and-forget BEFORE openURL
  return Linking.openURL(url);
}
```

Then update all 7+ call sites to pass the context dict (most already have `query` and `category` in scope).

---

## 3. Paywall view/dismiss (1 endpoint)

**Backend**: `POST /intelligence/paywall-event` (action: viewed|dismissed) in `server/app/features/intelligence_router.py`.

**RN files**:
- `src/components/UpgradePrompt.tsx` — main paywall component
- `src/components/LockedPreviewSection.tsx` — Pro-feature preview lock

**Trigger**:
- When `UpgradePrompt` mounts → `postPaywallEvent({ feature, action: "viewed" })`
- When user taps close/X without converting → `postPaywallEvent({ feature, action: "dismissed" })`

**Implementation** (helper in `src/api/intelligenceApi.ts`):
```ts
export async function postPaywallEvent(args: { feature: string; action: "viewed" | "dismissed" }) {
  try {
    await fetch(`${API_URL}/intelligence/paywall-event`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${jwt}` },
      body: JSON.stringify(args),
    });
  } catch {}
}
```

In UpgradePrompt:
```tsx
useEffect(() => { postPaywallEvent({ feature, action: "viewed" }); }, []);
const handleDismiss = () => {
  postPaywallEvent({ feature, action: "dismissed" });
  onClose();
};
```

The `feature` prop should be a stable key like `"deal_desk_pro"`, `"unlimited_alerts"`, `"sell_timing"`, etc.

---

## 4. Feature-gated attempt (1 endpoint)

**Backend**: `POST /intelligence/feature-attempt` in `server/app/features/intelligence_router.py`.

**RN file**: `src/hooks/useBillingLimits.ts` — this is THE place where Pro gates are enforced.

**Trigger**: every time a free-tier user hits a Pro-only check that returns false.

**Implementation**:
```ts
// inside useBillingLimits.ts where the gate decision happens
export function useBillingLimits() {
  const checkPro = (feature: string): boolean => {
    if (isProOrPremium) return true;
    // GATE FAILED — record the attempt before returning false
    postFeatureAttempt({ feature });
    return false;
  };
  return { checkPro, /* ...other limits */ };
}

async function postFeatureAttempt(args: { feature: string }) {
  try {
    await fetch(`${API_URL}/intelligence/feature-attempt`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${jwt}` },
      body: JSON.stringify(args),
    });
  } catch {}
}
```

The `feature` keys here should match the keys used in `paywall-event` so the two streams join cleanly in `/intelligence/top-paywall-rejections`.

---

## Verification after wiring

Once each endpoint has FE callers, verify with:

```bash
# Backend: check the demand_signals counts after the FE ships
ssh collectai 'cd /opt/collectors/server && set -a && source ../.env && set +a && ../.venv/bin/python -c "
import asyncio, asyncpg, os
async def m():
    c = await asyncpg.connect(os.environ[\"DB_DSN_DIRECT\"])
    rows = await c.fetch(\"SELECT signal_type, COUNT(*) c FROM demand_signals WHERE signal_type IN (\x27affiliate_click\x27,\x27paywall_viewed\x27,\x27paywall_dismissed\x27,\x27feature_gated_attempt\x27) GROUP BY signal_type\")
    for r in rows: print(r)
    rows = await c.fetch(\"SELECT \x27impressions\x27, COUNT(*) FROM notification_impressions UNION ALL SELECT \x27interactions\x27, COUNT(*) FROM notification_interactions UNION ALL SELECT \x27outcomes\x27, COUNT(*) FROM notification_outcomes\")
    for r in rows: print(r)
    await c.close()
asyncio.run(m())
"
```

All counts should start increasing within hours of users hitting the wired flows.

---

## Why these 6 in this order

1. Push impression/interaction (1a, 1b) — single file change, single hook, biggest data volume per user.
2. Affiliate-click (2) — single helper file, automatic propagation to 7+ components.
3. Paywall events (3) — only 2 components touch this, monetization-critical.
4. Feature-attempt (4) — single hook, monetization-critical.
5. Outcome (1c) — needs cross-app coordination, lowest data volume; ship last.

Total estimated FE work: 4-6 hours for someone fluent in the codebase.
