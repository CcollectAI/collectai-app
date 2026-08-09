/**
 * eBay Market Provider Adapter
 *
 * Uses the eBay Browse API (v1) for active listings and item lookup,
 * and the eBay Finding API for sold comparable searches.
 *
 * Auth: OAuth 2.0 client credentials flow using EBAY_CLIENT_ID and EBAY_CLIENT_SECRET.
 * Rate limit: 5000 calls/day (~83 RPM).
 */

import Constants from 'expo-constants';
import { logger } from '@/lib/logger';
import { toEUR } from '@/lib/fx';
import type { CurrencyCode, MarketHit } from '@/data/types';
import type {
  MarketProviderAdapter,
  ProviderMetadata,
  ProviderSearchOptions,
  ProviderSearchResult,
} from '../types';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EBAY_BROWSE_BASE = 'https://api.ebay.com/buy/browse/v1';
const EBAY_FINDING_BASE = 'https://svcs.ebay.com/services/search/FindingService/v1';

/** All 54 CollectAI categories */
const ALL_CATEGORIES = [
  'pokemon', 'mtg', 'yugioh', 'lorcana',
  'funko', 'designer_toys', 'anime_figures', 'hot_toys',
  'lego', 'gunpla', 'scale_models', 'warhammer',
  'retro_games', 'manga', 'bluray_steelbook', 'anime_bluray',
  'anime_soundtrack', 'anime_ost_vinyl', 'kpop_merch', 'taylor_swift',
  'pop_fandom', 'kpop_lightsticks', 'disney', 'theme_park',
  'ghibli', 'bandai_premium', 'jp_magazine', 'jp_event',
  'nintendo_merch', 'retro_pokemon', 'one_piece', 'vtuber',
  'keycaps', 'loungefly', 'diecast', 'sportscards',
];

const TAG = '[EbayAdapter]';

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
  // Expo Constants → app.config extra
  const extra = Constants.expoConfig?.extra as Record<string, unknown> | undefined;
  if (extra && typeof extra[key] === 'string') {
    return extra[key] as string;
  }
  // Fallback to process.env (works in Node/test environments)
  try {
    return (process.env as Record<string, string | undefined>)[key];
  } catch (e) {
    logger.error('[silent-catch] ebay-adapter.ts:66:', e);
    return undefined;
  }
}

function makeErrorResult(error: string, latencyMs: number): ProviderSearchResult {
  return { hits: [], totalAvailable: 0, success: false, error, latencyMs };
}

function convertPrice(price: number, fromCurrency: string): { price: number; currency: CurrencyCode } {
  const upper = fromCurrency.toUpperCase();
  if (upper === 'EUR') return { price, currency: 'EUR' };
  if (upper === 'USD') return { price: toEUR(price, 'USD'), currency: 'EUR' };
  // For other currencies, return as-is with original currency
  return { price, currency: upper as CurrencyCode };
}

// ---------------------------------------------------------------------------
// OAuth Token Management
// ---------------------------------------------------------------------------

let cachedToken: { token: string; expiresAt: number } | null = null;

async function getAccessToken(clientId: string, clientSecret: string): Promise<string> {
  // Return cached token if still valid (with 60s buffer)
  if (cachedToken && Date.now() < cachedToken.expiresAt - 60_000) {
    return cachedToken.token;
  }

  const credentials = btoa(`${clientId}:${clientSecret}`);

  const resp = await fetch('https://api.ebay.com/identity/v1/oauth2/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      Authorization: `Basic ${credentials}`,
    },
    body: 'grant_type=client_credentials&scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope',
  });

  if (!resp.ok) {
    const body = await resp.text().catch(() => '');
    throw new Error(`eBay OAuth failed (${resp.status}): ${body}`);
  }

  const data = (await resp.json()) as { access_token: string; expires_in: number };
  cachedToken = {
    token: data.access_token,
    expiresAt: Date.now() + data.expires_in * 1000,
  };

  return cachedToken.token;
}

// ---------------------------------------------------------------------------
// Response Normalization
// ---------------------------------------------------------------------------

function normalizeBrowseItem(item: Record<string, any>): MarketHit {
  const rawPrice = item.price?.value ? parseFloat(item.price.value) : 0;
  const rawCurrency = item.price?.currency ?? 'USD';
  const converted = convertPrice(rawPrice, rawCurrency);
  const rawId = item.itemId ?? '';

  return {
    source: 'ebay',
    rawId,
    title: item.title ?? '',
    price: converted.price,
    currency: converted.currency,
    soldAt: null,
    url: item.itemWebUrl ?? item.itemHref ?? null,
    condition: item.condition ?? item.conditionId ?? null,
    imageUrl: item.image?.imageUrl ?? item.thumbnailImages?.[0]?.imageUrl ?? null,
    rawPayloadHash: simpleHash(`ebay${rawId}`),
  };
}

function normalizeFindingItem(item: Record<string, any>): MarketHit {
  const rawPrice =
    item.sellingStatus?.[0]?.currentPrice?.[0]?.['__value__']
      ? parseFloat(item.sellingStatus[0].currentPrice[0]['__value__'])
      : 0;
  const rawCurrency =
    item.sellingStatus?.[0]?.currentPrice?.[0]?.['@currencyId'] ?? 'USD';
  const converted = convertPrice(rawPrice, rawCurrency);
  const rawId = item.itemId?.[0] ?? '';

  const endTime = item.listingInfo?.[0]?.endTime?.[0] ?? null;

  return {
    source: 'ebay',
    rawId,
    title: item.title?.[0] ?? '',
    price: converted.price,
    currency: converted.currency,
    soldAt: endTime,
    url: item.viewItemURL?.[0] ?? null,
    condition: item.condition?.[0]?.conditionDisplayName?.[0] ?? null,
    imageUrl: item.galleryURL?.[0] ?? null,
    rawPayloadHash: simpleHash(`ebay${rawId}`),
  };
}

// ---------------------------------------------------------------------------
// EbayAdapter Class
// ---------------------------------------------------------------------------

export class EbayAdapter implements MarketProviderAdapter {
  readonly metadata: ProviderMetadata = {
    id: 'ebay',
    name: 'eBay',
    supportedCategories: ALL_CATEGORIES,
    requiresApiKey: true,
    rateLimitRpm: 83,
    supportsSoldComps: true,
  };

  private clientId: string;
  private clientSecret: string;

  constructor(clientId?: string, clientSecret?: string) {
    this.clientId = clientId ?? getEnv('EBAY_CLIENT_ID') ?? '';
    this.clientSecret = clientSecret ?? getEnv('EBAY_CLIENT_SECRET') ?? '';
  }

  // -----------------------------------------------------------------------
  // Interface Methods
  // -----------------------------------------------------------------------

  async search(query: string, opts?: ProviderSearchOptions): Promise<ProviderSearchResult> {
    const start = Date.now();
    try {
      if (!this.clientId || !this.clientSecret) {
        return makeErrorResult('eBay API credentials not configured', Date.now() - start);
      }

      const token = await getAccessToken(this.clientId, this.clientSecret);
      const limit = opts?.limit ?? 20;

      // Build filter string
      const filters: string[] = [];
      if (opts?.minPrice != null) filters.push(`price:[${opts.minPrice}..`);
      if (opts?.maxPrice != null) {
        // Close or create range
        if (filters.length > 0 && filters[filters.length - 1].endsWith('..')) {
          filters[filters.length - 1] += `${opts.maxPrice}]`;
        } else {
          filters.push(`price:[..${opts.maxPrice}]`);
        }
      } else if (filters.length > 0 && filters[filters.length - 1].endsWith('..')) {
        // Close open-ended range
        filters[filters.length - 1] += ']';
      }

      const params = new URLSearchParams({
        q: query,
        limit: String(Math.min(limit, 200)), // eBay max is 200
      });
      if (filters.length > 0) {
        params.set('filter', filters.join(','));
      }

      const url = `${EBAY_BROWSE_BASE}/item_summary/search?${params.toString()}`;
      logger.debug(TAG, 'search', url);

      const resp = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-EBAY-C-MARKETPLACE-ID': opts?.region ?? 'EBAY_US',
          'Content-Type': 'application/json',
        },
      });

      if (resp.status === 429) {
        const retryAfter = resp.headers.get('Retry-After');
        logger.warn(TAG, `Rate limited. Retry-After: ${retryAfter ?? 'unknown'}`);
        return makeErrorResult('eBay rate limit exceeded', Date.now() - start);
      }

      if (!resp.ok) {
        const body = await resp.text().catch(() => '');
        logger.warn(TAG, `search failed (${resp.status}):`, body);
        return makeErrorResult(`eBay API error: ${resp.status}`, Date.now() - start);
      }

      const data = (await resp.json()) as {
        itemSummaries?: Record<string, any>[];
        total?: number;
      };

      const hits = (data.itemSummaries ?? []).map(normalizeBrowseItem);
      const totalAvailable = data.total ?? hits.length;

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
      if (!this.clientId || !this.clientSecret) {
        logger.warn(TAG, 'lookup: credentials not configured');
        return null;
      }

      const token = await getAccessToken(this.clientId, this.clientSecret);
      const url = `${EBAY_BROWSE_BASE}/item/${encodeURIComponent(rawId)}`;
      logger.debug(TAG, 'lookup', url);

      const resp = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US',
          'Content-Type': 'application/json',
        },
      });

      if (resp.status === 429) {
        logger.warn(TAG, 'lookup rate limited');
        return null;
      }

      if (!resp.ok) {
        if (resp.status === 404) {
          logger.debug(TAG, `Item ${rawId} not found`);
          return null;
        }
        logger.warn(TAG, `lookup failed (${resp.status})`);
        return null;
      }

      const item = (await resp.json()) as Record<string, any>;
      const hit = normalizeBrowseItem(item);
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
      if (!this.clientId || !this.clientSecret) {
        return makeErrorResult('eBay API credentials not configured', Date.now() - start);
      }

      // eBay Finding API (findCompletedItems) for sold items
      // Uses app-level auth via SECURITY-APPNAME parameter
      const limit = opts?.limit ?? 20;

      const params = new URLSearchParams({
        'OPERATION-NAME': 'findCompletedItems',
        'SERVICE-VERSION': '1.13.0',
        'SECURITY-APPNAME': this.clientId,
        'RESPONSE-DATA-FORMAT': 'JSON',
        'REST-PAYLOAD': '',
        'keywords': queryOrBarcode,
        'itemFilter(0).name': 'SoldItemsOnly',
        'itemFilter(0).value': 'true',
        'itemFilter(1).name': 'ListingType',
        'itemFilter(1).value(0)': 'FixedPrice',
        'itemFilter(1).value(1)': 'AuctionWithBIN',
        'paginationInput.entriesPerPage': String(Math.min(limit, 100)),
        'sortOrder': 'EndTimeSoonest',
      });

      // Optional price filters
      if (opts?.minPrice != null) {
        params.set('itemFilter(2).name', 'MinPrice');
        params.set('itemFilter(2).value', String(opts.minPrice));
        params.set('itemFilter(2).paramName', 'Currency');
        params.set('itemFilter(2).paramValue', 'USD');
      }
      if (opts?.maxPrice != null) {
        const idx = opts?.minPrice != null ? 3 : 2;
        params.set(`itemFilter(${idx}).name`, 'MaxPrice');
        params.set(`itemFilter(${idx}).value`, String(opts.maxPrice));
        params.set(`itemFilter(${idx}).paramName`, 'Currency');
        params.set(`itemFilter(${idx}).paramValue`, 'USD');
      }

      const url = `${EBAY_FINDING_BASE}?${params.toString()}`;
      logger.debug(TAG, 'soldComps', url);

      const resp = await fetch(url);

      if (resp.status === 429) {
        logger.warn(TAG, 'soldComps rate limited');
        return makeErrorResult('eBay rate limit exceeded', Date.now() - start);
      }

      if (!resp.ok) {
        const body = await resp.text().catch(() => '');
        logger.warn(TAG, `soldComps failed (${resp.status}):`, body);
        return makeErrorResult(`eBay Finding API error: ${resp.status}`, Date.now() - start);
      }

      const data = (await resp.json()) as Record<string, any>;

      const searchResult =
        data.findCompletedItemsResponse?.[0]?.searchResult?.[0];
      const items = searchResult?.item ?? [];
      const totalStr =
        data.findCompletedItemsResponse?.[0]?.paginationOutput?.[0]
          ?.totalEntries?.[0] ?? '0';

      const hits = (items as Record<string, any>[]).map(normalizeFindingItem);
      const totalAvailable = parseInt(totalStr, 10) || hits.length;

      return {
        hits,
        totalAvailable,
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
      const result = await this.search('collectible', { limit: 1 });
      return result.success;
    } catch (e) {
      logger.error('[silent-catch] ebay-adapter.ts:408:', e);
      return false;
    }
  }
}
