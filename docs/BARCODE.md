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
> **Decided 2026-09-26: no paid source (Merle).** Built instead, both free:
> 1. **Learned barcodes** — every save that began as a scan records what the
>    code turned out to be (`public.barcode_observations`, one row per member;
>    `server/app/lib/barcode_learning.py`). Written by `/intake/save` (it used
>    to accept `barcode` and drop it) and by `POST /intake/barcode-observation`
>    from manual add and QuickScan's draft save. The catalogue link is resolved
>    by the SERVER from the title, never taken from the client. A new cascade
>    tier after the catalogue reads it: a catalogue-linked answer is shared
>    with anyone (public data); a member's free-typed title only with that
>    member, or with others once TWO members agree. Product codes only
>    (EAN-8/UPC-A/EAN-13/GTIN-14) — a Code 128 serial names one object.
> 2. **Photo fallback** — an unrecognised scan offers "Identify from a photo";
>    QuickScan carries the barcode into whatever it saves, so the photo's
>    answer is learned for the code.
> Verified on prod: simcheck scans LEGO `5702015869935` → miss; saves it as
> "LEGO Millennium Falcon" → `{"recorded":true,"catalogue_match":true}`;
> simseller (another member) scans → "LEGO Millennium Falcon", lego,
> `75192-1-millennium-falcon`, `identification_method: barcode_learned`.
> Tests: `test_barcode_learning.py`, `barcodeResultCardPhoto.test.tsx`
> (privacy rule and the fallback button mutation-proven).
> **Walked through the emulator's CAMERA 2026-09-27** (generated EAN-13 as a
> virtual-scene poster — method in `docs/ANDROID_LAUNCH.md`): LEGO
> `5702015869935` → "Product Found · barcode learned", EUR 125, "Find on
> BrickLink" opens `bricklink.com/v2/search.page?q=…` (untagged: no affiliate
> ID); ISBN `9780439708180` → "Harry Potter…" via Open Library; unknown
> `4006381333931` → "Not recognised" + "Identify from a photo". Fixed on the
> way: "Identified via: manual" under "Not recognised"; the catalogue sheet
> said "We don't recognize this item yet" under "Product Found" for the ISBN
> (now "Not in our catalogue yet"); an old Add-manually draft overwrote the
> photo fallback's hand-off, dropping the barcode (so nothing was learned).
> ⚠️ The Falcon's PRICE (EUR 124.78, same as its catalogue page) is wrong
> data, not a lookup bug: its daily comps are EUR 74 / 175 with a latest of
> 20.77 — parts/minifigs matched as the set. See docs/OPEN_DECISIONS.md #4.

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
