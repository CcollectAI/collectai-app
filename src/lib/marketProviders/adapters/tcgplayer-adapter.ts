/**
 * TCGPlayer Market Provider Adapter
 *
 * Uses the TCGPlayer API v1.39.0 for searching TCG product catalogs
 * and retrieving market price data for sold comparables.
 *
 * Auth: Bearer token from TCGPLAYER_BEARER_TOKEN env var.
 * Rate limit: 300 RPM.
 *
 * Supported categories: pokemon, mtg, yugioh, lorcana.
 */

import Constants from 'expo-constants';
import { logger } from '@/lib/logger';
import { toEUR } from '@/lib/fx';
import type { MarketHit } from '@/data/types';
import type {
  MarketProviderAdapter,
  ProviderMetadata,
  ProviderSearchOptions,
  ProviderSearchResult,
} from '../types';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TCGPLAYER_BASE = 'https://api.tcgplayer.com/v1.39.0';

/** TCGPlayer group IDs for supported CollectAI categories */
const CATEGORY_TO_TCGPLAYER_ID: Record<string, number> = {
  pokemon: 3,
  mtg: 1,
  yugioh: 2,
  lorcana: 71,
};

const SUPPORTED_CATEGORIES = Object.keys(CATEGORY_TO_TCGPLAYER_ID);

const TAG = '[TCGPlayerAdapter]';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Simple deterministic hash for deduplication (DJB2 variant). */
function simpleHash(input: string): string {
  let hash = 5381;
  for (let i = 0; i < input.length; i++) {
    hash = ((hash << 5) + hash + input.charCodeAt(i)) | 0;
  }
  return (hash >>> 0).toString(16);
}

function getEnv(key: string): string | undefined {
  // Expo Constants -> app.config extra
  const extra = Constants.expoConfig?.extra as Record<string, unknown> | undefined;
  if (extra && typeof extra[key] === 'string') {
    return extra[key] as string;
  }
  // Fallback to process.env
  try {
    return (process.env as Record<string, string | undefined>)[key];
  } catch {
    return undefined;
  }
}

function makeErrorResult(error: string, latencyMs: number): ProviderSearchResult {
  return { hits: [], totalAvailable: 0, success: false, error, latencyMs };
}

function convertUsdToEur(usd: number): number {
  return toEUR(usd, 'USD');
}

// ---------------------------------------------------------------------------
// Response Normalization
// ---------------------------------------------------------------------------

function normalizeCatalogProduct(
  product: Record<string, any>,
  priceMap?: Map<number, Record<string, any>>,
): MarketHit {
  const productId = product.productId ?? product.productID ?? '';
  const rawId = String(productId);

  // Try to get market price from the price map if available
  const priceData = priceMap?.get(productId);
  const rawPrice = priceData?.marketPrice ?? priceData?.midPrice ?? product.marketPrice ?? 0;

  return {
    source: 'tcgplayer',
    rawId,
    title: product.name ?? product.productName ?? '',
    price: convertUsdToEur(rawPrice),
    currency: 'EUR',
    soldAt: null,
    url: product.url
      ? `https://www.tcgplayer.com${product.url}`
      : `https://www.tcgplayer.com/product/${rawId}`,
    condition: null,
    imageUrl: product.imageUrl ?? product.image ?? null,
    rawPayloadHash: simpleHash(`tcgplayer${rawId}`),
  };
}

function normalizePriceResult(
  priceEntry: Record<string, any>,
  productName?: string,
): MarketHit {
  const productId = priceEntry.productId ?? '';
  const rawId = String(productId);
  const rawPrice = priceEntry.marketPrice ?? priceEntry.midPrice ?? 0;
  const condition = priceEntry.subTypeName ?? priceEntry.condition ?? null;

  return {
    source: 'tcgplayer',
    rawId,
    title: productName ?? `TCGPlayer #${rawId}`,
    price: convertUsdToEur(rawPrice),
    currency: 'EUR',
    soldAt: priceEntry.lastUpdated ?? null,
    url: `https://www.tcgplayer.com/product/${rawId}`,
    condition,
    imageUrl: null,
    rawPayloadHash: simpleHash(`tcgplayer${rawId}${condition ?? ''}`),
  };
}

// ---------------------------------------------------------------------------
// TCGPlayerAdapter Class
// ---------------------------------------------------------------------------

export class TCGPlayerAdapter implements MarketProviderAdapter {
  readonly metadata: ProviderMetadata = {
    id: 'tcgplayer',
    name: 'TCGPlayer',
    supportedCategories: SUPPORTED_CATEGORIES,
    requiresApiKey: true,
    rateLimitRpm: 300,
    supportsSoldComps: true,
  };

  private bearerToken: string;

  constructor(bearerToken?: string) {
    this.bearerToken = bearerToken ?? getEnv('TCGPLAYER_BEARER_TOKEN') ?? '';
  }

  // -----------------------------------------------------------------------
  // Private Helpers
  // -----------------------------------------------------------------------

  private getHeaders(): Record<string, string> {
    return {
      Authorization: `Bearer ${this.bearerToken}`,
      Accept: 'application/json',
      'Content-Type': 'application/json',
    };
  }

  /**
   * Resolve the TCGPlayer categoryId from a CollectAI categoryId.
   * Returns undefined if no mapping exists.
   */
  private resolveTcgCategoryId(categoryId?: string): number | undefined {
    if (!categoryId) return undefined;
    return CATEGORY_TO_TCGPLAYER_ID[categoryId];
  }

  /**
   * Fetch market prices for a list of product IDs.
   * Returns a Map of productId -> price data.
   */
  private async fetchPrices(productIds: number[]): Promise<Map<number, Record<string, any>>> {
    const priceMap = new Map<number, Record<string, any>>();
    if (productIds.length === 0) return priceMap;

    try {
      const idStr = productIds.join(',');
      const url = `${TCGPLAYER_BASE}/pricing/product/${idStr}`;

      const resp = await fetch(url, { headers: this.getHeaders() });
      if (!resp.ok) {
        logger.warn(TAG, `fetchPrices failed (${resp.status})`);
        return priceMap;
      }

      const data = (await resp.json()) as { results?: Record<string, any>[] };
      for (const entry of data.results ?? []) {
        const pid = entry.productId;
        // Prefer "Normal" sub-type; keep first seen otherwise
        if (pid != null && (!priceMap.has(pid) || entry.subTypeName === 'Normal')) {
          priceMap.set(pid, entry);
        }
      }
    } catch (err) {
      logger.warn(TAG, 'fetchPrices error:', err instanceof Error ? err.message : String(err));
    }

    return priceMap;
  }

  // -----------------------------------------------------------------------
  // Interface Methods
  // -----------------------------------------------------------------------

  async search(query: string, opts?: ProviderSearchOptions): Promise<ProviderSearchResult> {
    const start = Date.now();
    try {
      if (!this.bearerToken) {
        return makeErrorResult('TCGPlayer bearer token not configured', Date.now() - start);
      }

      const limit = opts?.limit ?? 20;
      const tcgCategoryId = this.resolveTcgCategoryId(opts?.categoryId);

      // Step 1: Search catalog for products
      const params = new URLSearchParams({
        productName: query,
        limit: String(Math.min(limit, 100)),
        offset: '0',
      });
      if (tcgCategoryId != null) {
        params.set('categoryId', String(tcgCategoryId));
      }

      const catalogUrl = `${TCGPLAYER_BASE}/catalog/products?${params.toString()}`;
      logger.debug(TAG, 'search', catalogUrl);

      const resp = await fetch(catalogUrl, { headers: this.getHeaders() });

      if (resp.status === 429) {
        const retryAfter = resp.headers.get('Retry-After');
        logger.warn(TAG, `Rate limited. Retry-After: ${retryAfter ?? 'unknown'}`);
        return makeErrorResult('TCGPlayer rate limit exceeded', Date.now() - start);
      }

      if (!resp.ok) {
        const body = await resp.text().catch(() => '');
        logger.warn(TAG, `search failed (${resp.status}):`, body);
        return makeErrorResult(`TCGPlayer API error: ${resp.status}`, Date.now() - start);
      }

      const data = (await resp.json()) as {
        results?: Record<string, any>[];
        totalItems?: number;
      };

      const products = data.results ?? [];
      const totalAvailable = data.totalItems ?? products.length;

      // Step 2: Fetch prices for the returned products
      const productIds = products
        .map((p) => p.productId ?? p.productID)
        .filter((id): id is number => id != null);

      const priceMap = await this.fetchPrices(productIds);

      // Step 3: Normalize
      const hits = products.map((p) => normalizeCatalogProduct(p, priceMap));

      return {
        hits,
        totalAvailable,
        success: true,
        latencyMs: Date.now() - start,
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      logger.error(TAG, 'search error:', msg);
      return makeErrorResult(msg, Date.now() - start);
    }
  }

  async lookup(rawId: string): Promise<MarketHit | null> {
    const start = Date.now();
    try {
      if (!this.bearerToken) {
        logger.warn(TAG, 'lookup: bearer token not configured');
        return null;
      }

      const productId = parseInt(rawId, 10);
      if (isNaN(productId)) {
        logger.warn(TAG, `lookup: invalid productId "${rawId}"`);
        return null;
      }

      // Fetch product details
      const url = `${TCGPLAYER_BASE}/catalog/products/${productId}`;
      logger.debug(TAG, 'lookup', url);

      const resp = await fetch(url, { headers: this.getHeaders() });

      if (resp.status === 429) {
        logger.warn(TAG, 'lookup rate limited');
        return null;
      }

      if (!resp.ok) {
        if (resp.status === 404) {
          logger.debug(TAG, `Product ${rawId} not found`);
          return null;
        }
        logger.warn(TAG, `lookup failed (${resp.status})`);
        return null;
      }

      const data = (await resp.json()) as { results?: Record<string, any>[] };
      const product = data.results?.[0];
      if (!product) return null;

      // Fetch price for this product
      const priceMap = await this.fetchPrices([productId]);

      const hit = normalizeCatalogProduct(product, priceMap);
      logger.debug(TAG, `lookup complete in ${Date.now() - start}ms`);
      return hit;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      logger.error(TAG, 'lookup error:', msg);
      return null;
    }
  }

  async soldComps(
    queryOrBarcode: string,
    opts?: ProviderSearchOptions,
  ): Promise<ProviderSearchResult> {
    const start = Date.now();
    try {
      if (!this.bearerToken) {
        return makeErrorResult('TCGPlayer bearer token not configured', Date.now() - start);
      }

      // Step 1: Search for products to get IDs
      const searchResult = await this.search(queryOrBarcode, {
        ...opts,
        limit: opts?.limit ?? 10,
      });

      if (!searchResult.success || searchResult.hits.length === 0) {
        return {
          hits: [],
          totalAvailable: 0,
          success: searchResult.success,
          error: searchResult.error ?? 'No products found for sold comps',
          latencyMs: Date.now() - start,
        };
      }

      // Step 2: Get recent market prices for these products (acts as sold comps)
      const productIds = searchResult.hits
        .map((h) => parseInt(h.rawId, 10))
        .filter((id) => !isNaN(id));

      if (productIds.length === 0) {
        return {
          hits: [],
          totalAvailable: 0,
          success: true,
          latencyMs: Date.now() - start,
        };
      }

      // Fetch detailed pricing (includes all sub-types / conditions)
      const idStr = productIds.join(',');
      const priceUrl = `${TCGPLAYER_BASE}/pricing/product/${idStr}`;
      logger.debug(TAG, 'soldComps prices', priceUrl);

      const resp = await fetch(priceUrl, { headers: this.getHeaders() });

      if (resp.status === 429) {
        logger.warn(TAG, 'soldComps rate limited');
        return makeErrorResult('TCGPlayer rate limit exceeded', Date.now() - start);
      }

      if (!resp.ok) {
        logger.warn(TAG, `soldComps prices failed (${resp.status})`);
        return makeErrorResult(`TCGPlayer pricing error: ${resp.status}`, Date.now() - start);
      }

      const data = (await resp.json()) as { results?: Record<string, any>[] };
      const priceEntries = data.results ?? [];

      // Build a name lookup from the search results
      const nameMap = new Map<string, string>();
      for (const hit of searchResult.hits) {
        nameMap.set(hit.rawId, hit.title);
      }

      // Normalize price entries as sold comps
      const hits = priceEntries
        .filter((e) => e.marketPrice != null && e.marketPrice > 0)
        .map((e) => normalizePriceResult(e, nameMap.get(String(e.productId))));

      return {
        hits,
        totalAvailable: hits.length,
        success: true,
        latencyMs: Date.now() - start,
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      logger.error(TAG, 'soldComps error:', msg);
      return makeErrorResult(msg, Date.now() - start);
    }
  }

  async healthCheck(): Promise<boolean> {
    try {
      const result = await this.search('pikachu', { limit: 1, categoryId: 'pokemon' });
      return result.success;
    } catch {
      return false;
    }
  }
}
