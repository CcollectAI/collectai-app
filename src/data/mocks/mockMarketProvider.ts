/**
 * Mock market / barcode domain provider.
 */

import type {
  BarcodeLookupResult,
  MarketSearchOptions,
  MarketSearchResult,
  MarketHit,
} from '../types';
import { logger } from '@/lib/logger';

export async function lookupByBarcode(
  barcode: string,
  opts?: { codeType?: string },
): Promise<BarcodeLookupResult> {
  logger.info('[MockDataProvider] lookupByBarcode', { barcode, opts });

  const fixtures: Record<string, BarcodeLookupResult> = {
    '9781839063077': {
      title: 'Warhammer 40,000: Core Book (10th Edition)',
      categoryId: 'warhammer',
      subtypeId: 'rulebook',
      taxonomyVersion: 'v1.0',
      collections: [],
      attributes: {
        publisher: 'Games Workshop',
        isbn: '9781839063077',
        format: 'Hardcover',
        pages: 280,
      },
      missingRequired: [],
      priceBand: {
        q10: 45,
        q50: 55,
        q90: 65,
        confidence: 0.85,
        currency: 'EUR',
      },
      rationale: ['Matched ISBN to Games Workshop product catalog', 'Price from recent eBay sold comps'],
      barcode,
      barcodeType: opts?.codeType || 'isbn',
      imageUrl: null,
    },
    '8809848755491': {
      title: 'BTS - Proof (Standard Edition)',
      categoryId: 'music_media',
      subtypeId: 'album',
      taxonomyVersion: 'v1.0',
      collections: ['bts'],
      attributes: {
        artist: 'BTS',
        album: 'Proof',
        edition: 'Standard',
        format: 'CD Box Set',
        releaseYear: 2022,
        label: 'BigHit Entertainment',
      },
      missingRequired: [],
      priceBand: {
        q10: 35,
        q50: 55,
        q90: 85,
        confidence: 0.82,
        currency: 'EUR',
      },
      rationale: ['Matched to BTS anthology album', 'Collection tag: bts', 'Price from Discogs/eBay sold'],
      barcode,
      barcodeType: opts?.codeType || 'ean13',
      imageUrl: null,
    },
    '8809440339068': {
      title: 'BTS - Map of the Soul: 7',
      categoryId: 'music_media',
      subtypeId: 'album',
      taxonomyVersion: 'v1.0',
      collections: ['bts'],
      attributes: {
        artist: 'BTS',
        album: 'Map of the Soul: 7',
        format: 'CD',
        releaseYear: 2020,
        label: 'BigHit Entertainment',
      },
      missingRequired: [],
      priceBand: {
        q10: 20,
        q50: 35,
        q90: 60,
        confidence: 0.88,
        currency: 'EUR',
      },
      rationale: ['K-pop album matched via barcode', 'Collection tag: bts'],
      barcode,
      barcodeType: opts?.codeType || 'ean13',
      imageUrl: null,
    },
    '843930092451': {
      title: 'Taylor Swift Eras Tour Crewneck Sweater (Black, L)',
      categoryId: 'music_media',
      subtypeId: 'tour_merch',
      taxonomyVersion: 'v1.0',
      collections: ['taylor_swift', 'eras_tour'],
      attributes: {
        artist: 'Taylor Swift',
        tour: 'Eras Tour',
        itemType: 'Apparel',
        size: 'L',
        color: 'Black',
        year: 2023,
      },
      missingRequired: [],
      priceBand: {
        q10: 85,
        q50: 120,
        q90: 175,
        confidence: 0.75,
        currency: 'EUR',
      },
      rationale: ['Tour merch matched via UPC', 'Collections: taylor_swift, eras_tour', 'High demand item'],
      barcode,
      barcodeType: opts?.codeType || 'upc_a',
      imageUrl: null,
    },
    '602455542472': {
      title: 'Taylor Swift - 1989 (Taylor\'s Version) Vinyl LP',
      categoryId: 'music_media',
      subtypeId: 'vinyl',
      taxonomyVersion: 'v1.0',
      collections: ['taylor_swift'],
      attributes: {
        artist: 'Taylor Swift',
        album: '1989 (Taylor\'s Version)',
        format: 'Vinyl LP',
        releaseYear: 2023,
        label: 'Republic Records',
      },
      missingRequired: [],
      priceBand: {
        q10: 30,
        q50: 40,
        q90: 55,
        confidence: 0.9,
        currency: 'EUR',
      },
      rationale: ['Vinyl album matched via UPC', 'Collection tag: taylor_swift'],
      barcode,
      barcodeType: opts?.codeType || 'upc_a',
      imageUrl: null,
    },
    '9780593499597': {
      title: 'Fourth Wing (Hardcover)',
      categoryId: 'books',
      subtypeId: 'fiction',
      taxonomyVersion: 'v1.0',
      collections: [],
      attributes: {
        author: 'Rebecca Yarros',
        publisher: 'Red Tower Books',
        isbn: '9780593499597',
        format: 'Hardcover',
      },
      missingRequired: [],
      priceBand: {
        q10: 18,
        q50: 25,
        q90: 32,
        confidence: 0.92,
        currency: 'EUR',
      },
      rationale: ['ISBN matched via Open Library / Google Books'],
      barcode,
      barcodeType: opts?.codeType || 'isbn',
      imageUrl: null,
    },
  };

  if (fixtures[barcode]) {
    await new Promise((r) => setTimeout(r, 500));
    return fixtures[barcode];
  }

  await new Promise((r) => setTimeout(r, 300));
  return {
    title: null,
    categoryId: null,
    subtypeId: null,
    taxonomyVersion: 'v1.0',
    collections: [],
    attributes: {},
    missingRequired: ['title', 'categoryId'],
    priceBand: null,
    rationale: ['Barcode not found in product databases', 'Try manual search with keywords'],
    barcode,
    barcodeType: opts?.codeType || 'unknown',
    imageUrl: null,
  };
}

export async function marketSearch(
  query: string,
  opts?: MarketSearchOptions,
): Promise<MarketSearchResult> {
  logger.info('[MockDataProvider] marketSearch', { query, opts });

  await new Promise((r) => setTimeout(r, 400));

  const mockHits: MarketHit[] = [];
  const lowerQuery = query.toLowerCase();

  if (lowerQuery.includes('bts') || opts?.collections?.includes('bts')) {
    mockHits.push(
      {
        source: 'ebay',
        rawId: 'ebay-bts-001',
        title: 'BTS Proof Album Standard Edition Sealed',
        price: 52,
        currency: 'EUR',
        soldAt: '2026-01-28T14:30:00Z',
        url: 'https://ebay.com/itm/bts-proof-001',
        condition: 'New',
        imageUrl: null,
        rawPayloadHash: 'abc123',
      },
      {
        source: 'discogs',
        rawId: 'discogs-bts-002',
        title: 'BTS - Map of the Soul: 7 CD Box',
        price: 38,
        currency: 'EUR',
        soldAt: '2026-01-25T10:00:00Z',
        url: 'https://discogs.com/sell/item/bts-mots7',
        condition: 'Mint',
        imageUrl: null,
        rawPayloadHash: 'def456',
      },
    );
  }

  if (lowerQuery.includes('taylor') || lowerQuery.includes('swift') || opts?.collections?.includes('taylor_swift')) {
    mockHits.push(
      {
        source: 'ebay',
        rawId: 'ebay-ts-001',
        title: 'Taylor Swift Eras Tour Crewneck Black Large',
        price: 115,
        currency: 'EUR',
        soldAt: '2026-01-30T16:45:00Z',
        url: 'https://ebay.com/itm/ts-eras-001',
        condition: 'New with tags',
        imageUrl: null,
        rawPayloadHash: 'ghi789',
      },
      {
        source: 'ebay',
        rawId: 'ebay-ts-002',
        title: 'Taylor Swift 1989 TV Vinyl LP Sealed',
        price: 42,
        currency: 'EUR',
        soldAt: '2026-01-29T12:00:00Z',
        url: 'https://ebay.com/itm/ts-1989-001',
        condition: 'New',
        imageUrl: null,
        rawPayloadHash: 'jkl012',
      },
    );
  }

  if (lowerQuery.includes('warhammer') || lowerQuery.includes('40k') || opts?.categoryId === 'warhammer') {
    mockHits.push(
      {
        source: 'ebay',
        rawId: 'ebay-wh-001',
        title: 'Warhammer 40K Core Book 10th Edition',
        price: 52,
        currency: 'EUR',
        soldAt: '2026-01-27T09:15:00Z',
        url: 'https://ebay.com/itm/wh40k-core',
        condition: 'Like New',
        imageUrl: null,
        rawPayloadHash: 'mno345',
      },
    );
  }

  if (mockHits.length === 0 && query.length > 2) {
    mockHits.push(
      {
        source: 'ebay',
        rawId: `ebay-generic-${Date.now()}`,
        title: `${query} - Similar Item Found`,
        price: Math.floor(Math.random() * 100) + 20,
        currency: 'EUR',
        soldAt: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString(),
        url: null,
        condition: 'Used',
        imageUrl: null,
        rawPayloadHash: `generic-${Date.now()}`,
      },
    );
  }

  let filteredHits = mockHits;
  if (opts?.soldOnly) {
    filteredHits = filteredHits.filter((h) => h.soldAt);
  }
  if (opts?.minPrice !== undefined) {
    filteredHits = filteredHits.filter((h) => h.price >= opts.minPrice!);
  }
  if (opts?.maxPrice !== undefined) {
    filteredHits = filteredHits.filter((h) => h.price <= opts.maxPrice!);
  }
  if (opts?.limit) {
    filteredHits = filteredHits.slice(0, opts.limit);
  }

  return {
    hits: filteredHits,
    providers: ['ebay', 'discogs'],
    totalRaw: mockHits.length,
    confidence: mockHits.length > 0 ? 0.8 : 0.2,
  };
}
