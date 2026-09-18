import { listingsCountLabel } from '../../src/lib/listingsCountLabel';

describe('listingsCountLabel', () => {
  it('marks a partial count with + so the first page does not read as the total', () => {
    // 24 of 200 downloaded: "24 listings" is what the header used to say.
    expect(listingsCountLabel(24, true)).toBe('24+ listings');
  });

  it('prints a plain count once every page is loaded', () => {
    expect(listingsCountLabel(7, false)).toBe('7 listings');
  });

  it('says "1 listing" for exactly one, and nothing more to load', () => {
    expect(listingsCountLabel(1, false)).toBe('1 listing');
  });

  it('pluralises when one is loaded and more are waiting', () => {
    // The plural follows what exists, not the digit — "1+ listing" claims a
    // single listing and contradicts its own plus sign.
    expect(listingsCountLabel(1, true)).toBe('1+ listings');
  });

  it('handles an empty result without a + (the screen hides it, but the words are still right)', () => {
    expect(listingsCountLabel(0, false)).toBe('0 listings');
  });
});
