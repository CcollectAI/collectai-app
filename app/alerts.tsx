/**
 * `/alerts` — retired 2026-08-08, kept as a redirect.
 *
 * This screen rendered `alert_trigger_history` in a "Recent" tab while
 * `app/notifications.tsx` rendered `notification_history` — two screens for one
 * event, because `deal_discovery_worker` writes BOTH for every Target Hit
 * (`:225` and `:248`). Its second tab, "Rules", was empty by design:
 * `user_price_alerts` has no writer on purpose, and re-adding one has already
 * been the same bug three times (docs/alerts-and-insights.md).
 *
 * The file survives ONLY as a redirect. Deleting it outright left
 * `sparrow://alerts` rendering expo-router's "Page not found" — verified on the
 * simulator. Nothing in the repo still points here (checked), no stored
 * `deep_link` does (0 rows in prod), and the push handler was corrected the
 * same day. This exists for the referrer nobody enumerated: a push payload
 * built by an older binary still installed on someone's phone, a link pasted
 * into a QA script, a shared URL.
 *
 * A stub that lands on the merged screen costs ten lines. A dead end costs the
 * user the alert they tapped.
 */
import { Redirect } from 'expo-router';

export default function AlertsRedirect() {
  return <Redirect href="/notifications" />;
}
