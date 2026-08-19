/**
 * `items.category` is a SLUG column. The pickers speak display NAMES.
 *
 * The two vocabularies meet in exactly two places, and both were wrong or
 * fragile on 2026-08-19:
 *
 *  - READING: cards printed `item.category` straight, so every Magic card said
 *    "mtg". `formatCategoryName` is the one resolver.
 *  - WRITING: `app/item/[id].tsx` builds its picker from CATEGORY_OPTIONS,
 *    which are display names, and `updateItem` wrote the value verbatim. An
 *    edit would have put "Magic: The Gathering" into a slug column, and the
 *    item would then have vanished from /categories/mtg, from the category
 *    page's "your collection" rail and from getCategoryStore — while still
 *    looking perfectly correct on its own screen
 *    (learning_join_vocabulary_slug_vs_display_name).
 *
 * Measured on prod before the fix: 9 distinct values, all slugs, 0 display
 * names. Latent, not live — which is exactly when it is cheap to close.
 */
import {
  formatCategoryName,
  CATEGORY_NAME_TO_SLUG,
  CATEGORY_SLUG_TO_NAME,
} from '@/constants/categories';

describe('reading: slug -> display name', () => {
  it('resolves the curated name for a slug a reader would not recognise', () => {
    expect(formatCategoryName('mtg')).toBe('Magic: The Gathering');
    expect(formatCategoryName('lorcana')).toBe('Disney Lorcana');
    expect(formatCategoryName('yugioh')).toBe('Yu-Gi-Oh!');
  });

  // The exact 9 distinct `items.category` values on prod, 2026-08-19.
  const LIVE_SLUGS = ['pokemon', 'lorcana', 'lego', 'one_piece_tcg', 'mtg',
                      'yugioh', 'whiskey', 'taylor_swift', 'books'];

  it('renders every category value present in prod as readable text', () => {
    // The requirement is READABILITY, not registry membership. An earlier
    // version of this test asserted every live slug was in the registry and
    // failed on `books` — one prod item in an unregistered category, which the
    // fallback title-cases to "Books" perfectly well. Categories can also be
    // user-typed (CUSTOM_CATEGORY_SENTINEL), so registry membership is not a
    // property the app can promise; "never shows a raw slug" is.
    for (const slug of LIVE_SLUGS) {
      const shown = formatCategoryName(slug);
      expect(shown).not.toMatch(/_/);              // no snake_case on screen
      expect(shown[0]).toBe(shown[0].toUpperCase());
    }
  });

  it('uses the CURATED name wherever the registry has one', () => {
    // This is the half that matters for the reported problem: 'mtg' must not
    // title-case to "Mtg", it must resolve to "Magic: The Gathering".
    const registered = LIVE_SLUGS.filter((s) => CATEGORY_SLUG_TO_NAME[s]);
    expect(registered.length).toBeGreaterThanOrEqual(8);
    for (const slug of registered) {
      expect(formatCategoryName(slug)).toBe(CATEGORY_SLUG_TO_NAME[slug]);
    }
  });

  it('title-cases an unknown slug rather than showing it raw', () => {
    expect(formatCategoryName('some_new_thing')).toBe('Some New Thing');
  });

  it('renders nothing for an absent category, not "Undefined"', () => {
    expect(formatCategoryName(null)).toBe('');
    expect(formatCategoryName(undefined)).toBe('');
    expect(formatCategoryName('')).toBe('');
  });
});

describe('writing: display name -> slug', () => {
  it('maps every curated name back to its slug', () => {
    // This is the map `updateItem` normalises through. A name missing from it
    // is a name the picker can produce and the write cannot convert.
    expect(CATEGORY_NAME_TO_SLUG['Magic: The Gathering']).toBe('mtg');
    expect(CATEGORY_NAME_TO_SLUG['Disney Lorcana']).toBe('lorcana');
  });

  it('round-trips: every slug -> name -> slug returns the original', () => {
    const broken = Object.keys(CATEGORY_SLUG_TO_NAME).filter(
      (slug) => CATEGORY_NAME_TO_SLUG[CATEGORY_SLUG_TO_NAME[slug]] !== slug,
    );
    // A duplicate display name across two slugs would break this, and would
    // silently merge two categories on write.
    expect(broken).toEqual([]);
  });

  it('the normalisation is a no-op on a value that is already a slug', () => {
    // updateItem applies `CATEGORY_NAME_TO_SLUG[x] ?? x`, so a slug must not
    // be found in the name map — otherwise a correct value gets rewritten.
    expect(CATEGORY_NAME_TO_SLUG['mtg']).toBeUndefined();
    expect(CATEGORY_NAME_TO_SLUG['pokemon']).toBeUndefined();
  });
});
