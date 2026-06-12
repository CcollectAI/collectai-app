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
