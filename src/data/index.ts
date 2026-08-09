/**
 * DataProvider selector.
 *
 * Returns:
 * - MockDataProvider when EXPO_PUBLIC_SUPABASE_MODE is missing, "mock", or "off"
 * - SupabaseDataProvider when EXPO_PUBLIC_SUPABASE_MODE is "real"
 *
 * Usage:
 *   import { dataProvider } from '@/data';
 *   const summary = await dataProvider.getPortfolioSummary();
 */

import type { DataProvider } from './DataProvider';
import { mockDataProvider } from './MockDataProvider';
import { supabaseDataProvider } from './SupabaseDataProvider';
import { CachedDataProvider } from './CachedDataProvider';
import { dataLogger } from '@/lib/logger';

// Re-export types for convenience
export type {
  PaginationParams,
  PortfolioSummary,
  Item,
  WatchlistItem,
  CreateItemInput,
  CreateWatchlistInput,
  CreateWishlistInput, // Alias for backwards compatibility
  PublicUserProfile,
  QuickScanAttributes,
  QuickScanPrediction,
  QuickScanResult,
  QuickscanDraft,
  PersistedItem,
  SpotlightSlide,
  MiniUserProfile,
  CategoryStoreData,
  CategorySummary,
  CategoryMissingItem,
  AlertFeedItem,
  AlertRule,
  DmThread,
  DmRequest,
  DmMessage,
  DmThreadStatus,
  AnalyticsMetrics,
  BuildPaintProject,
  BuildPaintStep,
  BuildPaintNote,
  CreateBuildPaintProjectInput,
  // Barcode / Market Data types
  BarcodeLookupResult,
  MarketHit,
  MarketSearchOptions,
  MarketSearchResult,
  // Presence
  UserPresence,
  // Activity Feed
  ActivityFeedItem,
  ActivityType,
  // Deal Desk
  Offer,
  OfferEvent,
  OfferStatus,
  UserReputation,
} from './types';

export type { DataProvider } from './DataProvider';

/**
 * Determine which provider to use based on environment variable.
 *
 * Mock provider: when mode is missing, `mock`, or `off`.
 * Real Supabase provider: any other value (canonical: `real`, also accepts
 * `strict` since `src/api/config.ts` uses that term and `eas.json` ships
 * the `store`/`production`/`preview` build profiles with `strict`).
 *
 * Until 2026-05-22 this only matched `real` exactly, so every production
 * build that obeyed config.ts's guidance (`strict`) silently ran on mock.
 *
 * The selected provider is always wrapped in a CachedDataProvider that adds
 * a SQLite offline cache with stale-while-revalidate semantics.  The cache
 * is transparent — callers see the same DataProvider interface.
 */
function selectProvider(): DataProvider {
  // Defaulting to 'mock' when the env var is missing is only safe in dev. In a
  // release build a missing EXPO_PUBLIC_SUPABASE_MODE would have served the
  // ENTIRE app from MockDataProvider — fabricated items, portfolio and prices
  // presented as the user's real data — and the only trace was a
  // dataLogger.info, which release builds strip. eas.json does set 'strict' for
  // the real profiles, so this is a latent trap rather than a live bug, but the
  // failure mode is severe enough that it must not depend on one JSON key.
  const rawMode = process.env.EXPO_PUBLIC_SUPABASE_MODE;
  const mode = (rawMode ?? (__DEV__ ? 'mock' : 'strict')).toLowerCase();

  if (!rawMode && !__DEV__) {
    dataLogger.error(
      '[data] EXPO_PUBLIC_SUPABASE_MODE is missing in a release build — ' +
        'defaulting to strict (real backend) rather than serving mock data. ' +
        'Check the eas.json build profile.',
    );
  }

  let inner: DataProvider;

  if (mode !== 'mock' && mode !== 'off') {
    dataLogger.info(`Using SupabaseDataProvider (mode=${mode})`);
    inner = supabaseDataProvider;
  } else {
    // logger.error, not info: mock data in a release build is a serious
    // condition the user would otherwise have no way to detect.
    const log = __DEV__ ? dataLogger.info : dataLogger.error;
    log(`Using MockDataProvider (mode=${mode})`);
    inner = mockDataProvider;
  }

  dataLogger.info('Wrapping provider with CachedDataProvider (SQLite offline cache)');
  return new CachedDataProvider(inner);
}

/**
 * The active data provider instance.
 * UI components should import this and call its methods.
 */
export const dataProvider: DataProvider = selectProvider();
