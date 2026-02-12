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
} from './types';

export type { DataProvider } from './DataProvider';

/**
 * Determine which provider to use based on environment variable.
 * Default is "mock" — real Supabase only when explicitly set to "real".
 *
 * The selected provider is always wrapped in a CachedDataProvider that adds
 * a SQLite offline cache with stale-while-revalidate semantics.  The cache
 * is transparent — callers see the same DataProvider interface.
 */
function selectProvider(): DataProvider {
  const mode = (process.env.EXPO_PUBLIC_SUPABASE_MODE ?? 'mock').toLowerCase();

  let inner: DataProvider;

  if (mode === 'real') {
    dataLogger.info('Using SupabaseDataProvider (real mode)');
    inner = supabaseDataProvider;
  } else {
    // Default: mock, off, or any other value → use mock
    dataLogger.info('Using MockDataProvider (mock mode)');
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
