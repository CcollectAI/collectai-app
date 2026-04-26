/**
 * Intelligence + notification-feedback + affiliate-click APIs.
 *
 * All calls are **fire-and-forget** — they wrap `post()` in `.catch(noop)`
 * so a backend hiccup never breaks the user-facing flow that triggered them.
 * The cost of a missed signal is small; the cost of a thrown error in
 * push-handler / paywall-mount / link-tap is large.
 *
 * See docs/FE_INTELLIGENCE_WIRING.md for the design notes.
 */
import { post } from "./httpClient";

const noop = () => undefined;

// ---------------------------------------------------------------------------
// Notification feedback (push impression / interaction / outcome)
// ---------------------------------------------------------------------------

export function recordPushImpression(
  notificationId: string,
  clientContext?: Record<string, unknown>,
): void {
  post("/notifications/feedback/impression", {
    notification_id: notificationId,
    client_context: clientContext ?? {},
  }).catch(noop);
}

export function recordPushInteraction(
  notificationId: string,
  kind: "open" | "dismiss" | "action" | "swipe",
  meta?: Record<string, unknown>,
): void {
  post("/notifications/feedback/interaction", {
    notification_id: notificationId,
    kind,
    meta: meta ?? {},
  }).catch(noop);
}

export function recordPushOutcome(args: {
  notification_id: string;
  outcome: "converted" | "ignored" | "expired" | "other";
  action_type?: string;
  action_ref?: Record<string, unknown>;
  latency_seconds?: number;
}): void {
  post("/notifications/feedback/outcome", args).catch(noop);
}

// ---------------------------------------------------------------------------
// Affiliate-link click tracking
// ---------------------------------------------------------------------------

export function recordAffiliateClick(args: {
  source: string;
  query?: string;
  item_key?: string;
  category?: string;
}): void {
  post("/marketplace/affiliate-click", args).catch(noop);
}

// ---------------------------------------------------------------------------
// Paywall + feature-gate tracking
// ---------------------------------------------------------------------------

export function recordPaywallEvent(args: {
  feature: string;
  action: "viewed" | "dismissed";
}): void {
  post("/intelligence/paywall-event", args).catch(noop);
}

export function recordFeatureAttempt(feature: string): void {
  post("/intelligence/feature-attempt", { feature }).catch(noop);
}
