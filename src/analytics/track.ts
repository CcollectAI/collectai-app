/**
 * Analytics module — single choke-point for all event tracking.
 *
 * Uses PostHog under the hood with a guarded import so the app
 * works fine if the SDK is absent or no API key is configured.
 */

/* ---------- Types ---------- */

type AuthEvent =
  | { name: 'user_signed_up'; properties: { method: string } }
  | { name: 'user_logged_in'; properties: { method: string } }
  | { name: 'user_logged_out' }
  | { name: 'onboarding_completed'; properties?: { categories_selected?: number } }
  | { name: 'onboarding_slide_viewed'; properties: { slide: number } }
  | { name: 'onboarding_skipped'; properties: { skip_slide: number } };

type ItemEvent =
  | { name: 'item_added'; properties: { source: 'quickscan' | 'manual' | 'barcode'; category?: string } }
  | { name: 'item_viewed'; properties: { item_id: string; category?: string } };

type ScanEvent =
  | { name: 'quickscan_started' }
  | { name: 'quickscan_photo_taken' }
  | { name: 'quickscan_result_accepted'; properties?: { category?: string; confidence?: number } };

type MarketplaceEvent =
  | { name: 'marketplace_search'; properties: { query: string; result_count: number } }
  | { name: 'affiliate_link_opened'; properties: { domain: string } };

type WatchlistEvent =
  | { name: 'watchlist_item_added'; properties?: { category?: string } }
  | { name: 'watchlist_shared'; properties: { method: 'text' | 'csv'; itemCount: number } };

type EventEvent =
  | { name: 'event_rsvp'; properties: { event_id: string; status: string } };

type DealEvent =
  | { name: 'offer_created'; properties: { offer_id: string } }
  | { name: 'deal_completed'; properties: { offer_id: string } };

type SubscriptionEvent =
  | { name: 'subscription_screen_viewed' }
  | { name: 'subscription_upgrade_initiated'; properties: { plan: string } };

type SponsorEvent =
  | { name: 'sponsor_dashboard_viewed' }
  | { name: 'sponsor_company_registered' }
  | { name: 'sponsor_tier_selected'; properties: { tier: string } }
  | { name: 'sponsor_checkout_initiated'; properties: { tier: string; company_id: string } }
  | { name: 'sponsor_profile_updated' }
  | { name: 'sponsor_announcement_sent'; properties: { event_id: string } };

type QuickScanEnhancementEvent =
  | { name: 'quickscan_fast_path_used'; properties: { category?: string; confidence?: number } }
  | { name: 'scan_feedback_submitted'; properties: { session_id: string; field: string } }
  | { name: 'social_proof_viewed'; properties: { category?: string; collector_count?: number } }
  | { name: 'duplicate_detected'; properties: { category?: string; owned_count?: number } }
  | { name: 'condition_grade_viewed'; properties: { scale?: string; grade?: string } }
  | { name: 'edge_classification_used'; properties: { category?: string; method?: string } }
  | { name: 'multi_item_detected'; properties: { item_count?: number } }
  | { name: 'comparison_scan_completed'; properties: { categories?: string[] } };

export type AnalyticsEvent =
  | AuthEvent
  | ItemEvent
  | ScanEvent
  | MarketplaceEvent
  | WatchlistEvent
  | EventEvent
  | DealEvent
  | SubscriptionEvent
  | SponsorEvent
  | QuickScanEnhancementEvent;

/* ---------- PostHog handle ---------- */

type PostHogClient = {
  capture: (event: string, properties?: Record<string, unknown>) => void;
  identify: (userId: string, properties?: Record<string, unknown>) => void;
  reset: () => void;
  screen: (name: string, properties?: Record<string, unknown>) => void;
};

let posthog: PostHogClient | null = null;

/**
 * Initialise PostHog. Call once from root layout.
 * No-ops silently if the SDK is missing or key is empty.
 */
export function initAnalytics(apiKey: string | undefined, host?: string): void {
  if (!apiKey) return;
  try {
    const PostHog = require('posthog-react-native');
    posthog = new PostHog.PostHog(apiKey, { host: host ?? 'https://us.i.posthog.com' });
  } catch {
    // SDK not installed — analytics disabled
  }
}

/* ---------- Public API ---------- */

/** Track a typed analytics event. No-op when PostHog is unavailable. */
export function track(event: AnalyticsEvent): void {
  if (!posthog) return;
  const props = 'properties' in event ? event.properties : undefined;
  posthog.capture(event.name, props as Record<string, unknown> | undefined);
}

/** Identify the current user. Call on sign-in / auth restore. */
export function identifyUser(userId: string, traits?: Record<string, unknown>): void {
  if (!posthog) return;
  posthog.identify(userId, traits);
}

/** Reset identity. Call on sign-out. */
export function resetAnalytics(): void {
  if (!posthog) return;
  posthog.reset();
}

/** Track a screen view. Call from navigation listener. */
export function trackScreen(name: string, properties?: Record<string, unknown>): void {
  if (!posthog) return;
  posthog.screen(name, properties);
}
