/**
 * Ad Configuration
 *
 * Centralized ad unit IDs and placement rules.
 * All unit IDs are placeholders — replace with real AppLovin MAX unit IDs
 * when the account is set up.
 */

import type { AdConfig } from './provider';

// ── Ad Unit IDs (replace with real AppLovin MAX IDs) ─────────────────

const AD_UNITS = {
  /** Banner at bottom of items list */
  ITEMS_BANNER: 'PLACEHOLDER_BANNER_ITEMS',
  /** Banner on marketplace screen */
  MARKETPLACE_BANNER: 'PLACEHOLDER_BANNER_MARKETPLACE',
  /** Banner below portfolio chart */
  PORTFOLIO_BANNER: 'PLACEHOLDER_BANNER_PORTFOLIO',
  /** Native ad card in items list */
  ITEMS_NATIVE: 'PLACEHOLDER_NATIVE_ITEMS',
  /** Interstitial after scan/save flow */
  SCAN_INTERSTITIAL: 'PLACEHOLDER_INTERSTITIAL_SCAN',
} as const;

// ── Placement Configs ────────────────────────────────────────────────

export const AD_PLACEMENTS: Record<string, AdConfig> = {
  items_banner: {
    unitId: AD_UNITS.ITEMS_BANNER,
    format: 'banner',
    placement: 'items_list',
  },
  marketplace_banner: {
    unitId: AD_UNITS.MARKETPLACE_BANNER,
    format: 'banner',
    placement: 'marketplace',
  },
  portfolio_banner: {
    unitId: AD_UNITS.PORTFOLIO_BANNER,
    format: 'banner',
    placement: 'portfolio',
  },
  items_native: {
    unitId: AD_UNITS.ITEMS_NATIVE,
    format: 'native',
    placement: 'items_feed',
  },
  scan_interstitial: {
    unitId: AD_UNITS.SCAN_INTERSTITIAL,
    format: 'interstitial',
    placement: 'post_scan',
  },
};

// ── Throttle Rules ───────────────────────────────────────────────────

export const AD_THROTTLE = {
  /** Minimum seconds between interstitials */
  INTERSTITIAL_COOLDOWN_SEC: 180, // 3 minutes
  /** Show interstitial every N scans/saves */
  INTERSTITIAL_EVERY_N_ACTIONS: 3,
  /** Max interstitials per session */
  INTERSTITIAL_MAX_PER_SESSION: 5,
  /** Insert native ad every N items in a list */
  NATIVE_AD_INTERVAL: 10,
} as const;
