import { computeItemDelta } from '@/lib/portfolioAnalytics';

describe('computeItemDelta', () => {
  it('computes the gain on the seeded Rayquaza (paid 58 -> 94.58)', () => {
    const d = computeItemDelta(58, 94.58)!;
    expect(d.pl).toBeCloseTo(36.58, 2);
    expect(d.pct).toBeCloseTo(63.07, 1);
  });

  it('computes a loss', () => {
    const d = computeItemDelta(210, 45.19)!;
    expect(d.pl).toBeCloseTo(-164.81, 2);
    expect(d.pct).toBeCloseTo(-78.48, 1);
  });

  it('returns null when the member never entered a cost basis', () => {
    expect(computeItemDelta(null, 94.58)).toBeNull();
    expect(computeItemDelta(undefined, 94.58)).toBeNull();
  });

  it('returns null when the item has no valuation', () => {
    expect(computeItemDelta(58, null)).toBeNull();
  });

  it('returns null on a zero or negative basis rather than dividing by it', () => {
    expect(computeItemDelta(0, 94.58)).toBeNull();
    expect(computeItemDelta(-5, 94.58)).toBeNull();
  });

  it('returns null on non-finite input', () => {
    expect(computeItemDelta(NaN, 10)).toBeNull();
    expect(computeItemDelta(10, Infinity)).toBeNull();
  });

  it('reports break-even as zero, not as null', () => {
    const d = computeItemDelta(58, 58)!;
    expect(d.pl).toBe(0);
    expect(d.pct).toBe(0);
  });
});
