# Multi-Source Market Data Architecture

This document describes the provider-adapter framework for aggregating market data from multiple sources.

## TCG buyable coverage — the listings pass (2026-08-06)

**The problem.** Coverage for mtg/pokemon/yugioh was counted in *price rows*
(pokemon 311%, mtg 728%), and on that basis those categories were added to
`marketplace_scrape_scheduler.SKIP_CATEGORIES`. But Target Hit needs **offers**,
not prices. Measured over 7 days:

```
mtg      276,125 hits →      0 buyable   (100% scryfall)
pokemon  193,472 hits →      0 buyable   (tcgplayer + cardmarket)
yugioh   139,820 hits →      0 buyable   (cardmarket + tcgplayer)
warhammer 10,945 hits → 10,945 buyable   (crawl4ai + ebay)
lego       3,414 hits →  3,414 buyable   (100% ebay)
```

eBay is **not** category-gated (`"ebay": None` in `ADAPTER_CATEGORY_ROUTING`) —
it was simply never asked about these categories. Every eBay-fed category runs
85–100% buyable.

**The fix.** A separate, small pass in the same worker
(`_get_tcg_listing_items` + `_scrape_listings`), `TCG_LISTINGS_BATCH=3` per
cycle (~864 eBay calls/day, one adapter each). Watched items with a target
price come first; the rest round-robins the six TCG categories. It uses
`aggregate_search`, **not** `find_sold_comps` — eBay's sold path needs the
Marketplace Insights API we do not have, while search returns active listings
that persist with `is_listing = (ended_at IS NULL)`.

`only_adapters={"ebay"}` was added to `MarketplaceAgent.aggregate_search` for
this: a full fan-out on a TCG query re-queries the price feeds these categories
already have, and Cardmarket answers our scrape with a Cloudflare challenge.

### Three defences, and why each exists

Each was added **because the previous one was measured and found insufficient.**

1. **Qualified query** — `"<card> MTG Magic the Gathering card"`. The bare title
   `Bayou` returned, and persisted, 20 buyable `mtg` rows that were books and a
   NES cartridge ("Midnight Bayou — Hardcover", "The Adventures of Bayou Billy").
2. **Title gate** (`_is_plausible_tcg_listing`) — requires a category marker
   plus every card-name token, and rejects `custom/proxy/sleeve/token/alter/…`.
3. **Price band** — 0.35×–4× the item's median known price
   (`_get_reference_price`), **failing closed** when no reference exists. This is
   the one that works. After gate 2, eBay still returned "Bayou Dragonfly"
   (€1.20, different card), "Bayou Groff" (€1.55), "Bayou Token" (€1.73) and
   "MTG Card Sleeves — Bayou" (€19.49) — all containing both "Bayou" and "MTG",
   so no keyword rule can separate them.

Why this matters: those rows land under `item_ref = 'mtg:sum-283-bayou'`, which
is the snipe's **exact-identity** arm. A €1.20 novel would have fired a Target
Hit against an €8015 target reading "100% below your target" — the identical bug
removed on 2026-08-04. All test rows were deleted.

### Known limitation: printing precision

The gates make the pass safe, not exact. Verified with everything on:

- `mtg:sum-283-bayou` (Summer Magic, ref €8015) → **0 rows**. eBay only had
  Revised Bayou at €256–476; the band rejected all of it. Correct — a wrong
  printing is a wrong item.
- `pokemon swsh45sv-…-sv058` (Shining Fates SV058, ref ~€5) → 8 rows, all real
  Alcremie cards but from **other sets**. The band cannot separate printings
  that all cost €1–7.

So expensive cards self-protect and cheap ones do not. Residual harm is bounded:
a user is alerted about a different printing at a similar price. The real fix is
eBay's structured catalogue (EPID); **do not** attempt it with more keyword
rules — that was measured and it costs all of the yield for none of the
precision.

### Verified in production 2026-08-06

```
sum-283-bayou   20 hits, ALL rejected            -> 0 rows   (Summer Magic vs Revised printing)
5dn-120-eon-hub 20 hits,  2 rejected (band)      -> 18 rows  (all genuine Fifth Dawn #120)
base2-base2-1   20 hits, 19 rejected (band)      -> 1 row
```

Every persisted row was read individually, not counted. That is how the last
false positive was found: *"2 Pokemon TCG Mega Moonlit ex Tin Bundle Clefable &
Gengar Sealed New"* (EUR 45.05) landed against `pokemon:base2-base2-1` — a
sealed tin, not the Base Set 2 Clefable. It passed the category marker, the
name token **and** the price band, because a tin costs about what a rare single
costs. Only the product type separates them, hence the second half of
`_TCG_REJECT_TOKENS` (tin/bundle/booster/sealed/lot of/elite trainer/...).

Note the Eon Hub result also softens the printing worry above: when a card name
is distinctive, eBay sellers include the set ("Fifth Dawn", "5DN", "120/165")
and the matches are exact. The failure mode is confined to cards whose name is
generic or whose printings are indistinguishable by price.

### Separate outage found while verifying this (2026-08-06)

`lorcana`, `digimon` and `one_piece_tcg` were on SKIP_CATEGORIES on the strength
of the April snapshot, and had **zero market_hits, ever** — 24,404 catalog
items, 26 scrape attempts between them. Chain: tcgcsv fed those three, tcgcsv
has 403'd us since 2026-08-01, `market_hits` retention is 1 day, the rows aged
out and nothing replaced them, and the skip list kept the scraper away. They are
now removed from SKIP_CATEGORIES so the main scrape covers them.

mtg/pokemon/yugioh stay skipped — scryfall/cardmarket/tcgplayer still deliver
331k/229k/167k rows per 30 days, so the original starvation argument still holds
for them.

`TCG_LISTINGS_BATCH=0` disables the pass without a deploy.

## Overview

Sparrow Collect supports market data from multiple providers through a normalized adapter interface. This allows:

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
