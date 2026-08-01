/** When true, hides non-core screens (events, build & paint, sell, gamification, sponsor, twitch) */
export const BETA_MODE = false;

/**
 * When true, social-density UI is hidden because we don't have enough public
 * users yet. Surfaces affected: leaderboard, inbox/DMs, twitch hub, marketplace
 * "Find Collectors" search, event attendee lists. Routes remain reachable by
 * deep link so existing share links don't 404.
 *
 * Flip to false once we cross ~50 active public profiles. Keeping it true at
 * launch avoids the "1 entry on the leaderboard" / "0 attendees on every
 * event" ghost-town look. Future: wire to a runtime public-user-count probe
 * via PostHog remote flag.
 *
 * 2026-06-20: set to FALSE so chat/inbox/Find-Collectors are reachable for
 * hands-on testing (verifying chat + events end-to-end). REVISIT before the
 * public App Store launch — flip back to true (or wire the runtime probe) so
 * day-1 users don't see empty social surfaces.
 *
 * 2026-07-31: back to TRUE. That testing is done — chat inbox, DM request and
 * the full event create/RSVP/edit/cancel path were all verified end-to-end
 * against prod. The condition for flipping it back has been met and the
 * ghost-town risk is real: **0 of 24 profiles are currently discoverable**
 * (both public-profile views filter on a non-null display_name/username, and
 * every legacy row has neither), so a day-one user would open the leaderboard
 * and Find Collectors to nothing at all. Flip to false again once ~50 public
 * profiles exist — registration now writes username AND display_name, so real
 * signups do appear.
 */
export const COMMUNITY_GATED = true;

/**
 * Social login (Sign in with Apple / Google) on the auth screens.
 * OFF for launch — email/password only avoids App Store guideline 4.8 (offering
 * Google requires also offering Apple) and the "broken button" rejection risk
 * from showing providers not yet configured in Supabase. Flip to true once the
 * Apple Services-ID/key + Google OAuth client are set up in Supabase.
 */
export const SOCIAL_LOGIN_ENABLED = false;

/**
 * "Follow category" pill on the category header. Disabled pre-launch: the
 * follow write (POST /events/categories/{id}/follow) currently fails with a
 * client-side 401 (the recurring auth-token bug — see the auth diagnostics
 * work). Hiding it avoids surfacing a button that always errors. Flip back to
 * true once the 401 root cause is fixed and verified on device.
 */
export const CATEGORY_FOLLOW_ENABLED = false;

/**
 * "Comparable Sales" list on the item detail price section. Disabled for now:
 * the comp matching surfaces unrelated items — e.g. classical/other-artist
 * discogs pressings shown as comps for a Taylor Swift record, all at €0 — which
 * reads as broken and erodes trust in the app's valuations. Hiding it is better
 * than showing bad data. Flip back to true once comp matching is reliable and
 * verified on real items across categories.
 */
export const COMPARABLE_SALES_ENABLED = false;

/**
 * The multi-marketplace selling surface (Seller Dashboard, create-listing and
 * connect-account flows). OFF pre-launch: the whole path is a dead end today.
 *
 * - No marketplace account can actually be connected. `ConnectMarketplaceModal`
 *   collects a seller name, but there is no eBay OAuth flow behind it, and
 *   `GET /marketplace/listings/accounts` returns `[]` in prod.
 * - Sold comps, which is what would make listing prices meaningful, is stubbed:
 *   eBay revoked our Finding API access on 2026-04-26 (verified by OAuth probe;
 *   `server/app/agents/adapters/ebay_caller.py:387` returns `[]`). Migrating to
 *   the Marketplace Insights API needs an application to eBay.
 *
 * So a user who reaches this screen can create a listing that goes nowhere.
 * Gating the SCREEN rather than hiding entry points is deliberate: nothing in
 * the app links to `/sell/dashboard`, but it is still reachable by deep link —
 * the same mistake as the free-tier purchase mandates, which were unreachable
 * in the UI yet reachable via a Universal Link (see docs/MONETIZATION.md).
 *
 * Flip to true once a real eBay account can be connected end-to-end and sold
 * comps return data.
 */
export const SELLING_ENABLED = false;

/**
 * On-demand "Get fresh comps" live price-fetch (the thin-category prompt on the
 * item detail screen). OFF for now: the live fetch is backed by the paid
 * scrapers (Firecrawl / Scrape.do), which are quota-exhausted / killswitched,
 * so the button only ever reports "Live price-fetch is currently unavailable" —
 * a dead-end CTA that reads as broken. Hide the whole prompt until the fetch
 * path is live again, then flip back to true.
 */
export const LIVE_PRICE_FETCH_ENABLED = false;

export const featureFlags = {
  darkMode: false,
  FEATURE_HAPTICS_MICRO_ANIMATIONS: true,
  FEATURE_ACCESSIBILITY_ENHANCEMENTS: true,
  FEATURE_DATA_INSIGHTS_ALERTS: true,
  FEATURE_EXPLAINABLE_AI_INTERFACES: true,
  FEATURE_GESTURE_THUMB_NAVIGATION: true,
  FEATURE_ANALYTICS: true,
  // QuickScan enhancements
  FEATURE_QUICKSCAN_FAST_PATH: true,
  FEATURE_SCAN_FEEDBACK: true,
  FEATURE_SOCIAL_PROOF: true,
  FEATURE_DUPLICATE_DETECTION: true,
  FEATURE_CONDITION_GRADING: true,
  FEATURE_EDGE_CLASSIFICATION: true,
  FEATURE_VIEWFINDER_HINTS: true,
  FEATURE_MULTI_ITEM_SCAN: true,
  // Compare (A/B scan) retired — not needed for launch. The flag gates BOTH
  // the pill in CameraViewfinder and the capture branch in quickscan.tsx, so
  // turning it off removes the whole flow; the code stays for easy revival.
  FEATURE_COMPARISON_SCAN: false,
  // Ads — dark by default. Enable via PostHog remote flag or manually
  // when user threshold is reached. Free users only; paid = ad-free.
  FEATURE_ADS: false,
};
