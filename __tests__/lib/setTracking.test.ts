/**
 * Set-tracking coverage — the list that stops a paid screen lying.
 *
 * Measured on prod 2026-08-19: `category_items.set_name` coverage is 71-100%
 * across the six TCG categories and 0.0% — ZERO rows — in all 50 others, whose
 * catalogue rows are every one `source='seed'`. Completion needs a denominator,
 * so a category with no set names cannot report progress at all.
 *
 * Before this, `sets-to-complete` told every empty-handed member to "add more
 * items". For a whiskey or LEGO collector that is false instruction — and they
 * are paying for the screen.
 */
import {
  SET_TRACKING_CATEGORIES,
  isSetTrackingCategory,
  unsupportedSetCategories,
} from '@/constants/setTracking';

describe('set tracking coverage', () => {
  it('lists exactly the categories measured to carry set names', () => {
    expect([...SET_TRACKING_CATEGORIES].sort()).toEqual(
      ['digimon', 'lorcana', 'mtg', 'one_piece_tcg', 'pokemon', 'yugioh'].sort(),
    );
  });

  it('excludes the categories measured at 0.0% coverage', () => {
    // The four most likely to be added by optimism. lego especially: the
    // importer runs and writes 3,410 rows, but emits no set_name.
    for (const c of ['lego', 'whiskey', 'watches', 'warhammer']) {
      expect(isSetTrackingCategory(c)).toBe(false);
    }
  });

  it('is case- and whitespace-insensitive', () => {
    expect(isSetTrackingCategory(' Pokemon ')).toBe(true);
    expect(isSetTrackingCategory(null)).toBe(false);
    expect(isSetTrackingCategory(undefined)).toBe(false);
  });

  it('names the member OWN uncovered categories, deduped and in order', () => {
    const items = [
      { category: 'lego' },
      { category: 'pokemon' },
      { category: 'whiskey' },
      { category: 'lego' },
      { category: null },
    ];
    expect(unsupportedSetCategories(items)).toEqual(['lego', 'whiskey']);
  });

  it('returns nothing when every item is in a covered category', () => {
    // A TCG-only collector must keep the ordinary "add more items" empty
    // state — for them that instruction is TRUE.
    expect(
      unsupportedSetCategories([{ category: 'mtg' }, { category: 'pokemon' }]),
    ).toEqual([]);
  });
});
