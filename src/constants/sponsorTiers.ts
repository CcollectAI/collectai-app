/**
 * Sponsored-event tiers — the ONE copy of what each tier includes.
 *
 * Source of truth is docs/MONETIZATION.md §3, and every line below is a feature
 * that exists in the app today (checked 2026-09-14):
 *
 *   featured  → "Sponsored" badge + "by <company>" on the event card
 *               (app/(tabs)/events.tsx) and a sort boost in the feed — below the
 *               viewer’s followed categories (rpc_list_personalized_events_v1 ORDER BY).
 *   promoted  → a push to followers of the event's category
 *               (billing_router.py, tier in promoted/spotlight).
 *   spotlight → nothing beyond Promoted yet. The spec's "brand logo" and
 *               "analytics dashboard" are NOT built: `sponsorLogoUrl` is rendered
 *               nowhere and `getSponsorAnalytics` has no screen. So this tier
 *               lists only what it really adds, which is nothing — see the
 *               warning in MONETIZATION.md before activating Stripe prices.
 *
 * This list used to exist twice (app/sponsor/register.tsx and
 * TierPickerPanel.tsx), identically, and both sold "Homepage banner",
 * "Priority support", "Dedicated landing page", "Custom branding" and
 * "Advanced analytics" — none of which exist — with a "POPULAR" badge on a tier
 * nobody had ever bought.
 */
import type { SponsorTier } from '@/data/events';

export type SponsorTierInfo = { id: SponsorTier; name: string; features: string[] };

export const SPONSOR_TIERS: SponsorTierInfo[] = [
  {
    id: 'featured',
    name: 'Featured',
    features: ['"Sponsored" badge with your company name', 'Boosted in the events feed'],
  },
  {
    id: 'promoted',
    name: 'Promoted',
    features: ['Everything in Featured', 'Push notification to followers of the event’s category'],
  },
  {
    id: 'spotlight',
    name: 'Spotlight',
    features: ['Everything in Promoted'],
  },
];
