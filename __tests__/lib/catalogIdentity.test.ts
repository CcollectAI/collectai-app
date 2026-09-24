/**
 * Rows that share a title must say which one they are (2026-09-24: five
 * "Charizard ex" in search, indistinguishable, and the pick decides alerts).
 */
import { catalogIdentityLabel } from '@/lib/catalogIdentity';

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
