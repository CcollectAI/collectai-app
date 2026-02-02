/**
 * MarketProviderAdapter Interface
 *
 * Defines the contract for market data providers (eBay, TCGPlayer, Discogs, etc.).
 * Each adapter normalizes results to the common MarketHit shape.
 *
 * @see docs/MARKET_DATA.md for architecture overview
 */

import type { MarketHit, MarketSearchOptions } from '../../data/types';

/**
 * Search options specific to a single provider.
 * Extends the common options with provider-specific fields.
 */
export type ProviderSearchOptions = MarketSearchOptions & {
  /** Provider-specific: API key override */
  apiKey?: string;
  /** Provider-specific: Region/locale */
  region?: string;
  /** Provider-specific: Additional filters */
  providerFilters?: Record<string, unknown>;
};

/**
 * Result from a single provider search.
 */
export type ProviderSearchResult = {
  /** Normalized hits from this provider */
  hits: MarketHit[];
  /** Total results available (before limit) */
  totalAvailable: number;
  /** Whether the query succeeded */
  success: boolean;
  /** Error message if failed */
  error?: string;
  /** Response time in ms */
  latencyMs: number;
};

/**
 * Provider metadata for registration and health checks.
 */
export type ProviderMetadata = {
  /** Unique provider ID (e.g., 'ebay', 'tcgplayer') */
  id: string;
  /** Display name */
  name: string;
  /** Categories this provider is relevant for */
  supportedCategories: string[];
  /** Whether provider requires API key */
  requiresApiKey: boolean;
  /** Rate limit (requests per minute) */
  rateLimitRpm: number;
  /** Whether provider supports sold comps */
  supportsSoldComps: boolean;
};

/**
 * MarketProviderAdapter interface.
 *
 * Implement this interface to add a new market data source.
 * The aggregator will call all registered adapters and merge results.
 */
export interface MarketProviderAdapter {
  /**
   * Provider metadata for registration.
   */
  readonly metadata: ProviderMetadata;

  /**
   * Search for items matching query.
   * Returns normalized MarketHit results.
   *
   * @param query - Search query string
   * @param opts - Search options
   */
  search(query: string, opts?: ProviderSearchOptions): Promise<ProviderSearchResult>;

  /**
   * Lookup a single item by provider-specific ID.
   *
   * @param rawId - The provider's internal ID
   */
  lookup(rawId: string): Promise<MarketHit | null>;

  /**
   * Get sold comparables for price estimation.
   * Optional - not all providers support this.
   *
   * @param queryOrBarcode - Search query or barcode
   * @param opts - Search options
   */
  soldComps?(queryOrBarcode: string, opts?: ProviderSearchOptions): Promise<ProviderSearchResult>;

  /**
   * Health check - verify API connectivity.
   */
  healthCheck(): Promise<boolean>;
}

/**
 * Aggregator configuration.
 */
export type AggregatorConfig = {
  /** Max concurrent provider requests */
  maxConcurrency: number;
  /** Timeout per provider in ms */
  timeoutMs: number;
  /** Dedupe by rawPayloadHash */
  dedupeResults: boolean;
  /** Minimum confidence to include result */
  minConfidence: number;
};

/**
 * Default aggregator config.
 */
export const DEFAULT_AGGREGATOR_CONFIG: AggregatorConfig = {
  maxConcurrency: 3,
  timeoutMs: 5000,
  dedupeResults: true,
  minConfidence: 0.3,
};
