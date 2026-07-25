/**
 * Market Providers Module
 *
 * This module provides the MarketProviderAdapter interface and aggregator
 * for multi-source market data.
 *
 * @example
 * ```typescript
 * import { MarketProviderAdapter, aggregateSearch } from '@/lib/marketProviders';
 *
 * // Register adapters
 * const adapters: MarketProviderAdapter[] = [ebayAdapter, tcgPlayerAdapter];
 *
 * // Search across all providers
 * const results = await aggregateSearch(adapters, 'BTS Proof Album', { limit: 20 });
 * ```
 */

import type {
  MarketProviderAdapter,
  ProviderSearchOptions,
  AggregatorConfig,
} from './types';
import type { MarketSearchResult, MarketHit } from '../../data/types';
import { DEFAULT_AGGREGATOR_CONFIG } from './types';
import { logger } from '@/lib/logger';

export type {
  MarketProviderAdapter,
  ProviderSearchOptions,
  ProviderSearchResult,
  ProviderMetadata,
  AggregatorConfig,
} from './types';

export { DEFAULT_AGGREGATOR_CONFIG } from './types';

// Concrete adapter implementations
export { EbayAdapter, TCGPlayerAdapter, createAdapters } from './adapters';

/**
 * Aggregate search results from multiple providers.
 *
 * Calls all adapters in parallel, merges results, and dedupes.
 *
 * @param adapters - Array of provider adapters to query
 * @param query - Search query
 * @param opts - Search options
 * @param config - Aggregator configuration
 */
export async function aggregateSearch(
  adapters: MarketProviderAdapter[],
  query: string,
  opts?: ProviderSearchOptions,
  config: AggregatorConfig = DEFAULT_AGGREGATOR_CONFIG,
): Promise<MarketSearchResult> {
  if (adapters.length === 0) {
    return { hits: [], providers: [], totalRaw: 0, confidence: 0 };
  }

  // Execute searches in parallel with timeout
  const searchPromises = adapters.map(async (adapter) => {
    try {
      const timeoutPromise = new Promise<null>((resolve) =>
        setTimeout(() => resolve(null), config.timeoutMs)
      );

      const searchPromise = adapter.search(query, opts);
      const result = await Promise.race([searchPromise, timeoutPromise]);

      if (!result) {
        logger.warn(`[aggregateSearch] ${adapter.metadata.id} timed out`);
        return { adapter, result: null };
      }

      return { adapter, result };
    } catch (err) {
      logger.error(`[aggregateSearch] ${adapter.metadata.id} error:`, err);
      return { adapter, result: null };
    }
  });

  const results = await Promise.all(searchPromises);

  // Collect all hits
  let allHits: MarketHit[] = [];
  const providers: string[] = [];
  let totalRaw = 0;

  for (const { adapter, result } of results) {
    if (result?.success) {
      allHits = allHits.concat(result.hits);
      providers.push(adapter.metadata.id);
      totalRaw += result.totalAvailable;
    }
  }

  // Dedupe by rawPayloadHash if enabled
  if (config.dedupeResults) {
    const seen = new Set<string>();
    allHits = allHits.filter((hit) => {
      const key = hit.rawPayloadHash || `${hit.source}-${hit.rawId}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  // Sort by soldAt (most recent first) or price
  allHits.sort((a, b) => {
    if (a.soldAt && b.soldAt) {
      return new Date(b.soldAt).getTime() - new Date(a.soldAt).getTime();
    }
    return b.price - a.price;
  });

  // Calculate confidence based on provider coverage and result count
  const confidence = Math.min(
    1,
    (providers.length / adapters.length) * 0.5 +
    Math.min(allHits.length / 10, 0.5)
  );

  return {
    hits: allHits,
    providers,
    totalRaw,
    confidence,
  };
}

/**
 * Aggregate sold comps from providers that support it.
 *
 * @param adapters - Array of provider adapters
 * @param queryOrBarcode - Search query or barcode
 * @param opts - Search options
 */
export async function aggregateSoldComps(
  adapters: MarketProviderAdapter[],
  queryOrBarcode: string,
  opts?: ProviderSearchOptions,
): Promise<MarketSearchResult> {
  // Filter to adapters that support sold comps
  const soldCompsAdapters = adapters.filter(
    (a) => a.metadata.supportsSoldComps && typeof a.soldComps === 'function'
  );

  if (soldCompsAdapters.length === 0) {
    return { hits: [], providers: [], totalRaw: 0, confidence: 0 };
  }

  return aggregateSearch(
    soldCompsAdapters,
    queryOrBarcode,
    { ...opts, soldOnly: true },
  );
}
