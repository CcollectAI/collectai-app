/**
 * Rows that share a title must say which one they are (2026-09-24: five
 * "Charizard ex" in search, indistinguishable, and the pick decides alerts).
 */
import { catalogIdentityLabel, catalogIdentityWithBrand } from '@/lib/catalogIdentity';

describe('catalogIdentityLabel', () => {
  it('names set and card number for a TCG key', () => {
    expect(catalogIdentityLabel('svp', 'svp-svp-161')).toBe('SVP · #161');
    expect(catalogIdentityLabel('sv4pt5', 'sv4pt5-sv4pt5-054')).toBe('SV4PT5 · #54');
  });
  it('shows the set alone when the key does not end in a number', () => {
    expect(catalogIdentityLabel('75192', 'lego-millennium-falcon')).toBe('75192');
  });
  it('shows only the number when the set is a slug, not a code', () => {
    expect(catalogIdentityLabel('pokemon-tcg', 'pokemon-tcg-151-charizard-ex-sar-185')).toBe('#185');
    expect(catalogIdentityLabel('pokemon-collab', 'build-a-bear-x-pokemon-charizard-online-exclusive')).toBeNull();
  });
  it('says nothing without a set', () => {
    expect(catalogIdentityLabel(null, 'svp-svp-161')).toBeNull();
    expect(catalogIdentityLabel('  ', 'x')).toBeNull();
  });
});

describe('catalogIdentityLabel with a title (2026-09-25)', () => {
  it('drops a key suffix that is a price in the title, not a card number', () => {
    expect(catalogIdentityLabel('wotc', 'wotc-base-set-1st-edition-charizard-holo-4-psa-10-420k',
      'Base Set 1st Edition Charizard Holo #4 (PSA 10 ~$420K)')).toBe('WOTC');
  });
  it('keeps a real card number that the title states', () => {
    expect(catalogIdentityLabel('pokemon-tcg', 'pokemon-tcg-151-charizard-ex-sar-185', '151 Charizard ex SAR #185')).toBe('#185');
    expect(catalogIdentityLabel('svp', 'svp-svp-161', 'Charizard ex SVP - 161')).toBe('SVP · #161');
    expect(catalogIdentityLabel('sv4pt5', 'sv4pt5-sv4pt5-054', 'Charizard ex 054/091')).toBe('SV4PT5 · #54');
  });
});

describe('catalogIdentityWithBrand', () => {
  it('drops the brand when the set code is the brand', () => {
    expect(catalogIdentityWithBrand('wotc', 'wotc-base-set-booster-pack-charizard-art-sealed',
      'Base Set Booster Pack (Charizard Art) Sealed', 'WOTC')).toEqual(['WOTC']);
  });
  it('keeps a different brand', () => {
    expect(catalogIdentityWithBrand('svp', 'svp-svp-161', 'Charizard ex SVP - 161', 'Pokemon TCG')).toEqual(['SVP · #161', 'Pokemon TCG']);
  });
});
