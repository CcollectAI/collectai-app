/**
 * Market domain provider — barcode lookup and market search.
 */

import type {
  CurrencyCode,
  BarcodeLookupResult,
  MarketSearchOptions,
  MarketSearchResult,
} from '../types';
import { collectorsApi } from '../../api/collectorsApi';
import logger from '../../utils/logger';

export async function lookupByBarcode(
  barcode: string,
  opts?: { codeType?: string },
): Promise<BarcodeLookupResult> {
  logger.info('[SupabaseDataProvider] lookupByBarcode', { barcode, opts });

  try {
    const res = await collectorsApi.lookupByBarcode(barcode, opts?.codeType) as Record<string, unknown>;

    const priceBandRaw = res.price_band as Record<string, unknown> | null | undefined;
    return {
      title: (res.title as string | null) ?? null,
      categoryId: (res.category_id ?? res.categoryId) as string | null ?? null,
      subtypeId: (res.subtype_id ?? res.subtypeId) as string | null ?? null,
      taxonomyVersion: (res.taxonomy_version as string | null) ?? 'v1.0',
      collections: (res.collections as string[] | null) ?? [],
      attributes: (res.attributes as Record<string, unknown> | null) ?? {},
      missingRequired: (res.missing_required as string[] | null) ?? [],
      priceBand: priceBandRaw ? {
        q10: priceBandRaw.q10 as number,
        q50: priceBandRaw.q50 as number,
        q90: priceBandRaw.q90 as number,
        confidence: priceBandRaw.confidence as number,
        currency: (priceBandRaw.currency as CurrencyCode | null) ?? 'EUR',
      } : null,
      rationale: (res.rationale as string[] | null) ?? [],
      barcode,
      barcodeType: opts?.codeType ?? 'unknown',
      imageUrl: (res.image_url as string | null) ?? null,
    };
  } catch (err: unknown) {
    logger.warn('[SupabaseDataProvider] lookupByBarcode API error:', err);

    return {
      title: null,
      categoryId: null,
      subtypeId: null,
      taxonomyVersion: 'v1.0',
      collections: [],
      attributes: {},
      missingRequired: ['title', 'categoryId'],
      priceBand: null,
      rationale: ['Barcode lookup failed - try manual search'],
      barcode,
      barcodeType: opts?.codeType ?? 'unknown',
      imageUrl: null,
    };
  }
}

export async function marketSearch(
  query: string,
  opts?: MarketSearchOptions,
): Promise<MarketSearchResult> {
  logger.info('[SupabaseDataProvider] marketSearch', { query, opts });

  try {
    const res = await collectorsApi.marketSearch(query, {
      category_id: opts?.categoryId,
      subtype_id: opts?.subtypeId,
      collections: opts?.collections,
      limit: opts?.limit,
      sold_only: opts?.soldOnly,
      min_price: opts?.minPrice,
      max_price: opts?.maxPrice,
    }) as Record<string, unknown>;

    return {
      hits: ((res.hits as Record<string, unknown>[] | null) ?? []).map((hit: Record<string, unknown>) => ({
        source: hit.source as string,
        rawId: (hit.raw_id ?? hit.rawId) as string,
        title: hit.title as string,
        price: hit.price as number,
        currency: (hit.currency as CurrencyCode | null) ?? 'EUR',
        soldAt: (hit.sold_at ?? hit.soldAt ?? null) as string | null,
        url: (hit.url ?? null) as string | null,
        condition: (hit.condition ?? null) as string | null,
        imageUrl: (hit.image_url ?? hit.imageUrl ?? null) as string | null,
        rawPayloadHash: ((hit.raw_payload_hash ?? hit.rawPayloadHash) as string | undefined) ?? undefined,
      })),
      providers: (res.providers as string[] | null) ?? [],
      totalRaw: (res.total_raw ?? res.totalRaw) as number ?? 0,
      confidence: (res.confidence as number | null) ?? 0.5,
    };
  } catch (err: unknown) {
    logger.warn('[SupabaseDataProvider] marketSearch API error:', err);

    return {
      hits: [],
      providers: [],
      totalRaw: 0,
      confidence: 0,
    };
  }
}
