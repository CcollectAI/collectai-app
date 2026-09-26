# Barcode / ISBN Scanning

This document describes the barcode scanning feature for quick item entry.

> ⚠️ **Status measured 2026-09-26: only BOOKS resolve.** The overview below
> promises music albums and boxed products; nothing backs them.
> - Tier 1, local catalogue: `category_items.barcode` is empty in **every**
>   category (`select count(*) from category_items where barcode <> ''` → 0).
> - Tiers 2–3 are Open Library and Google Books — ISBN only.
> - Probed as a member via `/intake/barcode-only`: LEGO 75192's EAN
>   `5702015869935` → name null, catalog_miss; the ISBN `9780439708180` →
>   "Harry Potter and the sorcerer's stone", **category null** (the classifier
>   does not map it to a category).
> So scanning a LEGO box, a Funko Pop or a sealed TCG product always ends in
> the "suggest to catalogue" modal.
>
> **Decision open:** UPCitemdb's keyless trial (`api.upcitemdb.com/prod/trial/
> lookup?upc=`) resolved the LEGO EAN to "Lego 75192 Millennium Falcon" from
> EC2 — but the trial is 100 lookups/day/IP and meant for evaluation, so
> production use means their paid plan (or another EAN source), i.e. a cost
> and a third-party dependency. The resolved title would then go through the
> same catalogue title match QuickScan uses to land on `lego:75192-1-…`.
> Falsifier for "fixed": the LEGO EAN above returns a name and category_id.

## Overview

The barcode scanner provides a fast entry method for items with barcodes:
- Books (ISBN-10, ISBN-13)
- Music albums (EAN-13, UPC-A)
- Boxed products (EAN-13, UPC-A)

## User Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Add Tab    │ ──▶ │   Scanner   │ ──▶ │  Prefill    │ ──▶ │   Save /    │
│  Tap Card   │     │   Camera    │     │   Card      │     │  Watchlist  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

1. User taps "Scan barcode / ISBN" card on Add tab
2. Camera opens with barcode scanner overlay
3. Scanner detects barcode type and value
4. App calls `DataProvider.lookupByBarcode(code, { codeType })`
5. Prefill card shows matched product info:
   - Title
   - Category / Subtype
   - Collections (e.g., 'bts', 'taylor_swift')
   - Price estimate (q10/q50/q90)
6. User confirms to save or adds to watchlist

## Supported Barcode Types

| Type | Format | Use Case |
|------|--------|----------|
| ISBN-13 | 978xxxxxxxxxx | Books |
| ISBN-10 | xxxxxxxxxx | Legacy books |
| EAN-13 | xxxxxxxxxxxxx | European products |
| UPC-A | xxxxxxxxxxxx | US products |
| EAN-8 | xxxxxxxx | Small products |
| Code128 | Variable | Shipping labels |

## DataProvider Contract

### lookupByBarcode

```typescript
DataProvider.lookupByBarcode(
  barcode: string,
  opts?: { codeType?: string }
): Promise<BarcodeLookupResult>
```

### BarcodeLookupResult

```typescript
type BarcodeLookupResult = {
  title?: string | null;
  categoryId?: string | null;
  subtypeId?: string | null;
  taxonomyVersion?: string;
  collections?: string[];       // e.g., ['bts'], ['taylor_swift', 'eras_tour']
  attributes?: Record<string, unknown>;
  missingRequired?: string[];
  priceBand?: PriceBand | null;
  rationale?: string[];
  barcode?: string;
  barcodeType?: string;
  imageUrl?: string | null;
};
```

## Mock Fixtures

For development/testing, these barcodes return mock data:

| Barcode | Product | Category | Collections |
|---------|---------|----------|-------------|
| 9781839063077 | Warhammer 40K Core Book | warhammer | - |
| 8809848755491 | BTS - Proof (Standard) | music_media | bts |
| 8809440339068 | BTS - Map of the Soul: 7 | music_media | bts |
| 843930092451 | Taylor Swift Eras Tour Crewneck | music_media | taylor_swift, eras_tour |
| 602455542472 | Taylor Swift - 1989 TV Vinyl | music_media | taylor_swift |
| 9780593499597 | Fourth Wing (Book) | books | - |

## Collection Tags

Barcode lookup can return collection tags for artist/franchise grouping:

```typescript
collections: ['bts']                    // K-pop artist
collections: ['taylor_swift', 'eras_tour']  // Artist + tour
collections: ['warhammer_40k']          // Franchise
```

These tags are **orthogonal to categories** - a BTS album has:
- Category: `music_media`
- Subtype: `album`
- Collections: `['bts']`

A Taylor Swift tour shirt has:
- Category: `music_media`
- Subtype: `tour_merch`
- Collections: `['taylor_swift', 'eras_tour']`

## Error Handling

If barcode lookup fails:

1. `missingRequired` array indicates what's needed
2. UI shows "Not Found" state with options:
   - Try Again (rescan)
   - Add Manually (navigate to manual form)
3. Fallback: run `marketSearch()` with barcode as query

## Implementation Files

| File | Purpose |
|------|---------|
| `app/barcode-scan.tsx` | Scanner screen UI |
| `app/(tabs)/add.tsx` | Entry point card |
| `src/data/DataProvider.ts` | Interface definition |
| `src/data/MockDataProvider.ts` | Mock fixtures |
| `src/data/SupabaseDataProvider.ts` | Real API calls |

## Camera Permissions

The scanner uses `expo-camera` with these settings:

```typescript
barcodeScannerSettings={{
  barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e', 'code128'],
}}
```

Permission flow is handled in `barcode-scan.tsx` with proper fallback UI.

## Future Enhancements

- [ ] Batch scanning mode (scan multiple items quickly)
- [ ] Offline barcode cache for known products
- [ ] Manual barcode entry fallback
- [ ] Barcode history / recent scans
- [ ] Integration with inventory apps
