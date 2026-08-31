# Sparrow Collect Taxonomy System

## Overview

The taxonomy system provides a versioned, hierarchical classification for collectibles with two orthogonal concepts:

1. **Category/Subtype** - Drives schemas, pricing models, and prefill logic
2. **Collection Tags** - Drives UX grouping and special handling (e.g., "Taylor Swift", "BTS")

## Structure

```
Category (e.g., warhammer)
├── Subtype (e.g., warhammer_minis, warhammer_books)
│   └── Keywords (for automated mapping)
└── Collection Tags (orthogonal: taylor_swift, bts, disney, etc.)
```

## Category Waves

Categories are rolled out in phases:

| Wave | Categories | Description |
|------|------------|-------------|
| Phase 1 | pokemon, mtg, yugioh, funko, lorcana | Core TCG + Toys |
| Phase 2 | warhammer, gunpla, designer_toys, lego, diecast, sportscards | Hobby + Collectibles |
| Phase 3 | keycaps, retro_handhelds, loungefly, vinyl_records | Niche + Emerging |
| Special | music_memorabilia, apparel, instruments | Artist Collections |

## Files

- `src/taxonomy/registry.ts` - Category definitions, subtypes, collection tags
- `src/taxonomy/map.ts` - Deterministic mapper with confidence/rationale

## Usage

### Mapping an Item

```typescript
import { mapToTaxonomy } from '@/taxonomy/map';

const result = mapToTaxonomy({
  title: 'Warhammer 40k Space Marine Codex 9th Edition',
  isbn: '9781788269612',
});

// Result:
// {
//   categoryId: 'warhammer',
//   subtypeId: 'warhammer_books',
//   confidence: 0.95,
//   rationale: 'ISBN detected combined with Warhammer keywords → warhammer_books',
//   taxonomyVersion: '2026.02.02',
//   collections: [],
// }
```

### Detecting Collection Tags

```typescript
import { detectCollections } from '@/taxonomy/map';

const tags = detectCollections('Taylor Swift Eras Tour Hoodie Size M');
// Returns: [{ id: 'taylor_swift', name: 'Taylor Swift', ... }]
```

### Getting Category Info

```typescript
import { getCategoryById, getSubtypeById } from '@/taxonomy/registry';

const category = getCategoryById('warhammer');
const subtype = getSubtypeById('warhammer_books');
```

## Two vocabularies, and the one place they must meet (2026-08-19)

`items.category` stores a **SLUG** (`mtg`). Every picker in the app is built
from **display NAMES** (`Magic: The Gathering`). Both directions had a defect:

**Reading.** Cards printed `item.category` straight, so a Magic card's badge
said *"mtg"*. `formatCategoryName` (`src/constants/categories.ts`) is the one
resolver — curated name where the registry has one, title-cased otherwise, `''`
for null. It was already used by `ItemsListItem` and `WatchlistItemCard`; the
item **grid** card, the **detail** screen, search results, the Home movers,
QuickScan batch results, market movers and demand heat all printed the raw
value. All now resolve, and the grid badge is a real `CategoryPill` — the same
component the list card uses, so it also carries the category tint and taps
through to `/categories/[id]`.

**Writing.** `app/item/[id].tsx` builds its picker from `CATEGORY_OPTIONS`,
which are display names, and `updateItem` wrote the value **verbatim** into the
slug column. An edit would have stored `Magic: The Gathering`, and that item
would then have vanished from `/categories/mtg`, from the category page's
"YOUR COLLECTION" rail and from `getCategoryStore` — while still looking
perfectly correct on its own screen
(`learning_join_vocabulary_slug_vs_display_name`).

**Measured on prod before fixing: 9 distinct values, all slugs, 0 display
names.** Latent, not live — which is exactly when it is cheap to close.
`updateItem` now normalises through `CATEGORY_NAME_TO_SLUG` at the single write
chokepoint (normalising at the call site would leave the next caller exposed),
and `__tests__/lib/categoryVocabulary.test.ts` pins both directions plus the
round-trip, so a duplicate display name across two slugs — which would silently
merge two categories on write — fails the build.

One live value, `books`, is **not** in the registry and title-cases to "Books".
That is fine and the test asserts readability rather than registry membership:
categories can also be user-typed (`CUSTOM_CATEGORY_SENTINEL`), so membership is
not a property the app can promise. "Never shows a raw slug" is.

## `items.condition` follows this same rule (2026-08-31)

The category work above was reasoned through once; condition had the identical
defect and now uses the identical shape. `src/lib/conditionVocabulary.ts`:

| category | condition | role |
|---|---|---|
| `CATEGORY_NAME_TO_SLUG` | `CONDITION_NAME_TO_SLUG` | display name → slug, applied on WRITE |
| `formatCategoryName` | `formatConditionName` | resolve a value read straight from the column |
| `categoryDisplayName` | `conditionDisplayName` | resolve state a PICKER may have written into |

**Measured on prod before fixing** (the category note's own standard): two
vocabularies were live at once — `new_sealed` 10, `near_mint` 8, `mint` 5 from
the scan path (`app/ml/openai_vision.py` emits snake_case), against `Sealed`,
`Mint`, `NM`, `Good`, `Excellent` from the picker. Unlike the category case this
was **live, not latent**: `near_mint` rendered raw on the item card.

Two consequences worth keeping:

- **`sameCondition()` exists because equality was wrong.** `ListForSaleModal`
  compared `condition === c` against its own Title Case list, so a scanned item
  never matched and silently lost its pre-selection. Any cross-vocabulary
  comparison must normalise both sides.
- **Graded values are not slugs.** `PSA 9` / `BGS 10` pass through every
  resolver untouched, the same way `books` title-cases without being in the
  category registry. Membership is not a property either column can promise.

Condition additionally varies BY CATEGORY, which category does not:
`conditionOptionsFor(category)` returns sealed/opened for boxed collectibles,
fill-and-seal for spirits, Goldmine for vinyl, card grading otherwise. A single
list could not say SEALED, so a sealed LEGO set and an opened one were both
"Mint" — see docs/COLLECTOR_DEMAND.md §7.

⚠️ **Vinyl is half-solved on purpose.** Goldmine grades the SLEEVE and the DISC
separately and this column is single-valued, so the sleeve grade belongs in
notes until there is a second field. That is the Discogs complaint in
COLLECTOR_DEMAND §2, and pretending one field covers it would be the overclaim
this file exists to prevent.

### When one variable holds BOTH vocabularies (2026-08-23)

`formatCategoryName` is the resolver when the value provably came out of
`items.category`. `app/item/[id].tsx` is the case where that is not knowable:
`editableCategory` is seeded from the saved row (a **slug**) and the picker
writes a display **NAME** back into the same state.

`formatCategoryName` is **not idempotent** — it title-cases on separators, so
`'Yu-Gi-Oh!'` comes back as `'Yu Gi Oh!'`. Applying it eagerly to that state
fixes the pre-pick render and corrupts the post-pick one.

`categoryDisplayName(value)` handles either: a value found in
`CATEGORY_NAME_TO_SLUG` is already a display name and is returned untouched,
anything else goes through `formatCategoryName`. That is the same map
`updateItem` normalises through (`CATEGORY_NAME_TO_SLUG[x] ?? x`), so the read
and the write cannot disagree about which vocabulary a value is in.

**Use `formatCategoryName` for a value read straight from the column;
`categoryDisplayName` for anything a picker may have written into.**

Found because the item card's edit-mode dropdown rendered `yugioh` — the
2026-08-19 sweep above fixed the read branch of that screen and never looked at
the edit branch.

## Mapping Rules

### Warhammer Books vs Miniatures

The mapper uses keyword matching to disambiguate:

**Books indicators:**
- ISBN present (strong signal)
- Keywords: codex, rulebook, battletome, black library, novel, lore

**Miniatures indicators:**
- Keywords: sprue, citadel, mini, 28mm, resin, assembled, painted, nos, nib

### Taylor Swift (Cross-Category)

Taylor Swift items span multiple categories:
- Apparel (hoodies, shirts) → `apparel/apparel_tops`
- Music (CDs, vinyl) → `music_memorabilia/music_albums`
- Instruments (signed guitars) → `instruments/instruments_signed`

The collection tag `taylor_swift` is always applied regardless of category.

## Extending the Taxonomy

### Adding a New Category

1. Add to `registry.ts` in the appropriate wave array
2. Define subtypes with keywords
3. Update tests in `__tests__/taxonomy.test.ts`

```typescript
const NEW_CATEGORY: CategoryDefinition = {
  id: 'new_category',
  name: 'New Category',
  wave: 'phase3',
  subtypes: [
    { id: 'new_subtype', name: 'Subtype', keywords: ['keyword1', 'keyword2'] },
  ],
};
```

### Adding a Collection Tag

```typescript
const NEW_TAG: CollectionTag = {
  id: 'new_tag',
  name: 'Display Name',
  aliases: ['alias1', 'alias2'],
  description: 'Description for users',
};
```

## Versioning

The taxonomy version (`TAXONOMY_VERSION`) should be bumped when:
- Adding new categories or subtypes
- Changing keyword mappings
- Modifying collection tags

Items store `taxonomy_version` so we can track which version classified them.

## Best Practices

1. **Always provide rationale** - Never silently ambiguous
2. **Use confidence scores** - 0.0-1.0, surface low confidence for review
3. **Prefer specificity** - Better to be specific than generic
4. **Test edge cases** - Especially for disambiguation (books vs minis)

---

## What belongs in a category's CATALOG (2026-08-04)

`category_items` is the browsable "what exists in this category" catalog, not a
product feed. The tcgcsv importer feeds six of the categories
(`mtg`, `pokemon`, `yugioh`, `lorcana`, `digimon`, `one_piece_tcg`) and it
ingests **TCGPlayer's full product list per game** — which is not a list of
cards. Lorcana alone carried 85 "Puzzle Insert" rows (the cardboard spacer
inside a booster box) plus playmats, sleeves, deck boxes and binders. Those rows
also hold the catalog's only broken art (their TCGPlayer CDN URLs 403), so they
surfaced in the browse grid as black tiles.

`GET /catalog/{category}/items` now filters them out. Filtered at **read**, not
deleted — rows stay for provenance, and `?include_accessories=true` restores
them.

### Two rules, both measured against the live catalog

Naming a product type is **not** sufficient. TCGPlayer sells promo *cards* named
after the accessory they shipped with, and a bare-term filter hid 34 of them.

1. **A product puts `:` or `-` straight after the item type.**
   `Official Playmat: Boa Hancock`, `Official Card Sleeves - Elsa (65 count)`.
   A promo card only mentions it, usually in parentheses:
   `Monkey.D.Luffy (Official Playmat Limited Edition Vol.5)`.
2. **A bracket whose contents start with a LETTER is a card-set code** —
   `[OP-PR]`, `[BT-17]`, `[EX-02]`, `[MP25]`. That row is a card whatever it is
   named after. Puzzle inserts carry numeric-only set numbers (`[11]`, `[6]`),
   so this guard doesn't touch them.

`Puzzle Insert` is exempt from rule 1 — it is never a card and appears
mid-title.

Result: **194 rows hidden across the six categories, 0 real cards among them.**

### Two false-positive classes this cost

Both were found by sampling the would-be-hidden rows **per category**, not by
trusting the total — the same discipline as
`learning_validate_values_not_just_structure`.

- **Bare `Binder` matched 36 rows; only 2 were accessories.** The other 34 are
  real cards: 14 Digimon and 13 One Piece promos from "Omnimon" / "Seven
  Warlords of the Sea" **Binder Set** releases, MTG's *Dihada, Binder of Wills*
  and *Fiend Binder*, and 5 printings of Yu-Gi-Oh's *Maliss Q White Binder*.
  A 94% false-positive rate — the filter would have hidden far more cards than
  filler.
- **Merch categories must not be filtered at all.** A first pass ran
  catalogue-wide and would have hidden `Pokemon Base Set Binder (1999)` and
  `Southern Islands Complete Binder Set (18 Cards)` from `retro_pokemon`, and
  `Pikachu Leather Deck Box` from `nintendo_merch`. **In a merch category the
  accessory IS the collectible.** Hence `_ACCESSORY_FILTERED_CATEGORIES`.

### Deliberately NOT filtered

Sealed product — Booster Box, Booster Pack, Bundle, Display. Sealed is a
collected format and the taxonomy has an explicit `*_sealed` subtype for it.
Removing it from browse is a product decision, not a data-quality fix.

**Before widening `_ACCESSORY_TERMS`, re-measure.** Run the candidate regex
against `category_items` per category and read every match — the term that looks
obviously safe is the one that eats a card name.
