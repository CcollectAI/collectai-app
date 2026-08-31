/**
 * Mirrors __tests__/lib/categoryVocabulary.test.ts, because items.condition has
 * the same two-vocabularies-one-column defect and docs/TAXONOMY.md already
 * reasons the fix through. Pins BOTH directions plus the round-trip: a
 * duplicate display name across two slugs would silently merge two conditions
 * on write, exactly as it would for categories.
 */
import {
  CONDITION_LABELS, CONDITION_NAME_TO_SLUG, conditionOptionsFor,
  formatConditionName, conditionDisplayName, toConditionSlug, sameCondition,
} from '@/lib/conditionVocabulary';

describe('the map itself', () => {
  it('every slug round-trips slug -> name -> slug', () => {
    for (const slug of Object.keys(CONDITION_LABELS)) {
      expect(toConditionSlug(CONDITION_LABELS[slug])).toBe(slug);
    }
  });
  it('no display name maps to two different slugs', () => {
    // The failure this guards: two conditions silently merging on write.
    const names = Object.values(CONDITION_LABELS);
    expect(new Set(names).size).toBe(names.length);
  });
});

describe('never shows a raw slug (docs/TAXONOMY.md)', () => {
  it('resolves the values actually in prod', () => {
    expect(formatConditionName('near_mint')).toBe('Near Mint');
    expect(formatConditionName('new_sealed')).toBe('New / Sealed');
    expect(formatConditionName('very_good')).toBe('Very Good');
  });
  it('title-cases an UNKNOWN slug rather than printing it raw', () => {
    expect(formatConditionName('mint_in_box')).toBe('Mint In Box');
  });
  it('leaves a graded value untouched — PSA 9 is not a slug', () => {
    expect(formatConditionName('PSA 9')).toBe('PSA 9');
    expect(formatConditionName('BGS 10')).toBe('BGS 10');
    expect(toConditionSlug('PSA 9')).toBe('PSA 9');
  });
  it('empty in, empty out', () => {
    expect(formatConditionName(null)).toBe('');
    expect(formatConditionName('')).toBe('');
    expect(toConditionSlug('   ')).toBeNull();
  });
});

describe('conditionDisplayName — state holding EITHER vocabulary', () => {
  it('returns a display name untouched (the picker just wrote it)', () => {
    // formatConditionName alone would be wrong here; this is why the second
    // function exists, same as categoryDisplayName.
    expect(conditionDisplayName('Near Mint')).toBe('Near Mint');
    expect(conditionDisplayName('New / Sealed')).toBe('New / Sealed');
  });
  it('resolves a slug seeded from the column', () => {
    expect(conditionDisplayName('near_mint')).toBe('Near Mint');
  });
});

describe('legacy spellings found in the column', () => {
  it.each([['NM', 'near_mint'], ['Sealed', 'new_sealed'], ['Brand New', 'new_sealed']])(
    '%s normalises to %s', (raw, slug) => expect(toConditionSlug(raw)).toBe(slug));
});

describe('sameCondition — the ListForSaleModal bug', () => {
  it('a SCANNED item matches the picker option that means the same thing', () => {
    // `condition === c` was false for near_mint vs 'Near Mint', so the sell
    // modal silently lost the pre-selection on every scanned item.
    expect(sameCondition('near_mint', 'Near Mint')).toBe(true);
    expect(sameCondition('NM', 'Near Mint')).toBe(true);
  });
  it('still distinguishes genuinely different conditions', () => {
    expect(sameCondition('mint', 'Near Mint')).toBe(false);
    expect(sameCondition('new_sealed', 'opened_complete')).toBe(false);
  });
  it('null never equals null — absence is not a match', () => {
    expect(sameCondition(null, null)).toBe(false);
    expect(sameCondition(null, 'Mint')).toBe(false);
  });
});

describe('per-category vocabularies (docs/COLLECTOR_DEMAND.md §7)', () => {
  it('boxed collectibles can say SEALED — the whole point', () => {
    for (const cat of ['lego', 'funko', 'anime_figures', 'jewellery', 'fragrances']) {
      expect(conditionOptionsFor(cat)).toContain('new_sealed');
    }
  });
  it('a sealed LEGO set and an opened one are no longer both "Mint"', () => {
    const lego = conditionOptionsFor('lego');
    expect(lego).toContain('new_sealed');
    expect(lego).toContain('opened_complete');
    expect(lego).not.toContain('near_mint');
  });
  it('TCG keeps card grading', () => {
    expect(conditionOptionsFor('pokemon')).toEqual(
      expect.arrayContaining(['mint', 'near_mint', 'excellent']));
    expect(conditionOptionsFor('pokemon')).not.toContain('new_sealed');
  });
  it('spirits get fill and seal, not surface wear', () => {
    expect(conditionOptionsFor('whiskey')).toContain('sealed_full');
    expect(conditionOptionsFor('whiskey')).toContain('opened_bottle');
  });
  it('vinyl gets Goldmine grades', () => {
    expect(conditionOptionsFor('vinyl_records')).toContain('vg_plus');
  });
  it('an unknown or null category falls back to card grading, never empty', () => {
    // An empty option list would render a picker with nothing in it.
    expect(conditionOptionsFor('some_new_category').length).toBeGreaterThan(0);
    expect(conditionOptionsFor(null).length).toBeGreaterThan(0);
  });
  it('every offered slug has a label — no picker can render a raw slug', () => {
    for (const cat of ['lego', 'pokemon', 'whiskey', 'vinyl_records', null]) {
      for (const slug of conditionOptionsFor(cat)) {
        expect(CONDITION_LABELS[slug]).toBeTruthy();
      }
    }
  });
});
