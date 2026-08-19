/**
 * ValueSourceChip — what the app is allowed to CLAIM about a number.
 *
 * `v_item_values_v1.value_source` says which link of the value chain answered.
 * The chip turns that into words a member reads, so a wrong mapping here is the
 * app asserting a hand-typed guess is a market price — the exact thing the
 * column was added to stop.
 *
 * Pure mapping only: `describeValueSource` is exported so this can be asserted
 * without rendering, and so the two surfaces (item detail, list row) cannot
 * describe the same number two different ways.
 */
import { describeValueSource, isMarketBacked } from '@/components/ValueSourceChip';

describe('value source wording', () => {
  it('calls the catalogue-backed sources a market estimate', () => {
    for (const s of ['catalog_daily', 'catalog_model', 'quick_scan']) {
      expect(describeValueSource(s)).toEqual({ label: 'Market estimate', tone: 'market' });
    }
  });

  it("never blames the member for the app's own guess", () => {
    // A vision scan produced it, so "your estimate" would be false — the
    // member did not say it.
    expect(describeValueSource('app_estimate')).toEqual({
      label: 'App estimate',
      tone: 'estimate',
    });
  });

  it('calls a typed number the member\'s own', () => {
    expect(describeValueSource('user_estimate')).toEqual({
      label: 'Your estimate',
      tone: 'estimate',
    });
  });

  it('says "not priced yet" when nothing answered', () => {
    // `none` means value_eur fell through to 0. Rendering "€0.00" with no
    // caveat is the unknown-as-zero class in words.
    expect(describeValueSource('none')?.label).toBe('Not priced yet');
  });

  it('claims NOTHING for an unknown or missing source', () => {
    // Undefined reaches here when the view read failed or a caller mapped its
    // own item shape. Guessing a provenance is worse than showing none.
    for (const s of [undefined, null, '', 'something_new']) {
      expect(describeValueSource(s as string | null | undefined)).toBeNull();
    }
  });
});

describe('market-backed boundary', () => {
  it('is exactly the comp/model sources', () => {
    // This boundary is what the leaderboard filters on — market truth only,
    // no self-reported figures. Widening it silently would let a typed number
    // into a public ranking.
    expect(['catalog_daily', 'catalog_model', 'quick_scan'].every(isMarketBacked)).toBe(true);
    expect(['user_estimate', 'app_estimate', 'none', undefined, null].some(isMarketBacked)).toBe(false);
  });
});
