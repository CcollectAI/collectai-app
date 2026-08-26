/**
 * `rankPositions` — the analytics "Positions" card's ranking.
 *
 * Why this file exists: this function decides which numbers a member is shown
 * as PROFIT. `/portfolio/items` falls back to the earliest PREDICTION as cost
 * basis when an item has no purchase price, so `unrealizedPL` on those rows is
 * model drift arriving in the same field, with the same shape, as real profit.
 * The only thing separating them is `hasPurchasePrice`, and a regression there
 * is silent — the card would still render, still rank, and be wrong.
 */
import { rankPositions } from '@/lib/portfolioAnalytics';

const pos = (
  id: string,
  hasPurchasePrice: boolean,
  costBasis: number,
  unrealizedPL: number,
) => ({ id, hasPurchasePrice, costBasis, unrealizedPL });

describe('rankPositions', () => {
  it('EXCLUDES items with no real purchase price, even when their P/L is the largest', () => {
    const r = rankPositions([
      pos('real', true, 100, 50),
      // Model drift. Biggest number on the screen, and it is not profit.
      pos('drift', false, 500, 900),
    ]);
    expect(r.ranked.map((p) => p.id)).toEqual(['real']);
    expect(r.counted).toBe(1);
    expect(r.missingBasis).toBe(1);
  });

  it('sorts by ABSOLUTE move, so a loss can lead', () => {
    const r = rankPositions([
      pos('gain', true, 100, 50),
      pos('loss', true, 200, -120),
      pos('small', true, 300, 10),
    ]);
    expect(r.ranked.map((p) => p.id)).toEqual(['loss', 'gain', 'small']);
  });

  it('excludes a zero cost basis — the caller divides by it', () => {
    const r = rankPositions([pos('zero', true, 0, 99)]);
    expect(r.ranked).toHaveLength(0);
    expect(r.counted).toBe(0);
    expect(r.missingBasis).toBe(1);
  });

  it('excludes an undefined unrealizedPL rather than ranking it as 0', () => {
    const r = rankPositions([
      { id: 'nopl', hasPurchasePrice: true, costBasis: 100 },
      pos('ok', true, 100, 5),
    ]);
    expect(r.ranked.map((p) => p.id)).toEqual(['ok']);
  });

  it('counts EVERY unranked item in missingBasis, so the card cannot imply the ranking is the whole collection', () => {
    const r = rankPositions([
      pos('a', true, 100, 10),
      pos('b', false, 100, 10),
      pos('c', false, 100, 10),
      pos('d', true, 0, 10),
    ]);
    expect(r.counted).toBe(1);
    expect(r.missingBasis).toBe(3);
  });

  it('honours the limit without changing the counts it reports', () => {
    const many = Array.from({ length: 10 }, (_, i) => pos(`i${i}`, true, 100, i + 1));
    const r = rankPositions(many, 6);
    expect(r.ranked).toHaveLength(6);
    expect(r.counted).toBe(10);
    expect(r.missingBasis).toBe(0);
  });
});
