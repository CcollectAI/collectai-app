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
  const mode = (process.env.EXPO_PUBLIC_SUPABASE_MODE ?? 'mock').toLowerCase();

  let inner: DataProvider;

  if (mode !== 'mock' && mode !== 'off') {
    dataLogger.info(`Using SupabaseDataProvider (mode=${mode})`);
    inner = supabaseDataProvider;
  } else {
    dataLogger.info(`Using MockDataProvider (mode=${mode})`);
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
