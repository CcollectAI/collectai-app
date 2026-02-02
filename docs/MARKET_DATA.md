# Multi-Source Market Data Architecture

This document describes the provider-adapter framework for aggregating market data from multiple sources.

## Overview

CollectAI supports market data from multiple providers through a normalized adapter interface. This allows:

- Adding new data sources without changing UI code
- Aggregating and deduplicating results across providers
- Provider-specific rate limiting and error handling
- Fallback behavior when providers are unavailable

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    DataProvider                          │
│  - marketSearch(query, opts) → MarketSearchResult       │
│  - lookupByBarcode(code, opts) → BarcodeLookupResult    │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│                    Aggregator                            │
│  - Calls all registered adapters in parallel            │
│  - Merges and dedupes results                           │
│  - Calculates confidence scores                         │
└─────────────────┬───────────────────────────────────────┘
                  │
      ┌───────────┼───────────┬───────────┐
      ▼           ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  eBay    │ │TCGPlayer │ │ Discogs  │ │  Future  │
│ Adapter  │ │ Adapter  │ │ Adapter  │ │ Adapters │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

## Key Types

### MarketHit

Normalized market listing from any provider:

```typescript
type MarketHit = {
  source: string;         // 'ebay', 'tcgplayer', 'discogs'
  rawId: string;          // Provider's listing ID
  title: string;
  price: number;
  currency: string;       // EUR, USD, GBP
  soldAt?: string | null; // Sale date if sold
  url?: string | null;
  condition?: string | null;
  imageUrl?: string | null;
  rawPayloadHash?: string; // For deduplication
};
```

### MarketSearchResult

Aggregated result from all providers:

```typescript
type MarketSearchResult = {
  hits: MarketHit[];
  providers: string[];    // Which providers responded
  totalRaw: number;       // Total before deduplication
  confidence: number;     // 0-1 confidence score
};
```

### MarketProviderAdapter

Interface for implementing a new provider:

```typescript
interface MarketProviderAdapter {
  readonly metadata: ProviderMetadata;
  search(query: string, opts?: ProviderSearchOptions): Promise<ProviderSearchResult>;
  lookup(rawId: string): Promise<MarketHit | null>;
  soldComps?(queryOrBarcode: string, opts?: ProviderSearchOptions): Promise<ProviderSearchResult>;
  healthCheck(): Promise<boolean>;
}
```

## Adding a New Provider

1. Create adapter file in `src/lib/marketProviders/adapters/`:

```typescript
// src/lib/marketProviders/adapters/myProvider.ts
import type { MarketProviderAdapter, ProviderMetadata } from '../types';

export const myProviderAdapter: MarketProviderAdapter = {
  metadata: {
    id: 'my_provider',
    name: 'My Provider',
    supportedCategories: ['pokemon', 'mtg'],
    requiresApiKey: true,
    rateLimitRpm: 60,
    supportsSoldComps: true,
  },

  async search(query, opts) {
    // Implement API call and normalize results
    const response = await fetch(...);
    return {
      hits: response.data.map(normalizeHit),
      totalAvailable: response.total,
      success: true,
      latencyMs: Date.now() - start,
    };
  },

  async lookup(rawId) {
    // Implement single item lookup
  },

  async soldComps(query, opts) {
    // Implement sold comparables (optional)
  },

  async healthCheck() {
    // Verify API connectivity
  },
};
```

2. Register adapter in aggregator configuration

## Planned Providers

| Provider | Status | Categories | Notes |
|----------|--------|------------|-------|
| eBay | Planned | All | Primary source for sold comps |
| TCGPlayer | Planned | TCG (MTG, Pokémon, Lorcana) | Partner API required |
| Discogs | Planned | Music (vinyl, CDs) | Good for BTS/Taylor Swift |
| Cardmarket | Planned | TCG (EU focused) | Regional pricing |
| ISBN/Books API | Planned | Books | Open Library, Google Books |

## Usage in UI

All UI components should use `DataProvider.marketSearch()`:

```typescript
// In a component
import { dataProvider } from '@/data';

const results = await dataProvider.marketSearch('BTS Proof Album', {
  collections: ['bts'],
  soldOnly: true,
  limit: 20,
});

// Display results
results.hits.forEach(hit => {
  console.log(`${hit.title}: €${hit.price} on ${hit.source}`);
});
```

## Configuration

Environment variables:

```
EXPO_PUBLIC_MARKET_EBAY_APP_ID=       # eBay API app ID
EXPO_PUBLIC_MARKET_TCGPLAYER_KEY=     # TCGPlayer API key
EXPO_PUBLIC_MARKET_DISCOGS_TOKEN=     # Discogs personal token
```

## Stop Conditions

- **No scraping**: All providers must use official APIs or partner agreements
- **ToS compliance**: Never violate provider terms of service
- **Rate limiting**: Respect provider rate limits
- **No mobile API keys**: Backend handles all API calls; mobile app uses presigned URLs
