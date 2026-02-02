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
import { dataLogger } from '@/lib/logger';

// Re-export types for convenience
export type {
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
 */
function selectProvider(): DataProvider {
  const mode = (process.env.EXPO_PUBLIC_SUPABASE_MODE ?? 'mock').toLowerCase();

  if (mode === 'real') {
    dataLogger.info('Using SupabaseDataProvider (real mode)');
    return supabaseDataProvider;
  }

  // Default: mock, off, or any other value → use mock
  dataLogger.info('Using MockDataProvider (mock mode)');
  return mockDataProvider;
}

/**
 * The active data provider instance.
 * UI components should import this and call its methods.
 */
export const dataProvider: DataProvider = selectProvider();
