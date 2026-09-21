/**
 * The Portfolio Tier, driven from PRODUCTION INPUT SHAPES.
 *
 * Why this file exists: the eight tier tests in
 * __tests__/components/analytics.test.tsx each hand the badge a hand-made
 * `makeTierSummary('Diamond')`. Not one drives `computeTierFromScores` from
 * anything an account could actually produce — so all eight stayed green for
 * the five weeks the card showed "Unranked" to every real member, and would
 * have stayed green forever. A suite is evidence only about what it asserts.
 *
 * The bug: `/portfolio/items` never returned `rarity_score` and
 * `/portfolio/overview` never returned set completion, so rarity and
 * completeness were pinned at 0. composite = 0.5*0 + 0.3*0 + 0.2*d ≤ 0.20,
 * and Silver starts at 0.30.
 */
import {
  computePortfolioSnapshot,
  computeTierFromScores,
  type PortfolioItemSnapshot,
} from '@/analytics/portfolioMetrics';

function item(over: Partial<PortfolioItemSnapshot> = {}): PortfolioItemSnapshot {
  return {
    id: Math.random().toString(36).slice(2),
    name: 'Card',
    category: 'pokemon',
    quantity: 1,
    currentValue: 100,
    ...over,
  };
}

describe('the ceiling that made every account Unranked', () => {
  it('is real: with rarity and completeness at 0, perfect diversity is still Unranked', () => {
    for (let d = 0; d <= 100; d++) {
      expect(computeTierFromScores(0, 0, d / 100).tier).toBe('Unranked');
    }
  });

  it('CONTROL — the tier can leave Unranked once rarity is served', () => {
    expect(computeTierFromScores(0.6, 0, 1).tier).not.toBe('Unranked');
  });
});

describe('a portfolio the server now describes fully', () => {
  const items = [
    item({ category: 'pokemon', collection: 'Base Set', setSize: 4, rarityScore: 0.9, raritySource: 'catalog' }),
    item({ category: 'pokemon', collection: 'Base Set', setSize: 4, rarityScore: 0.82, raritySource: 'catalog' }),
    item({ category: 'pokemon', collection: 'Base Set', setSize: 4, rarityScore: 0.98, raritySource: 'catalog' }),
    item({ category: 'funko', collection: 'NYCC', setSize: 2, rarityScore: 0.9, raritySource: 'item', currentValue: 90 }),
  ];

  it('leaves Unranked — the whole point of the change', () => {
    const snap = computePortfolioSnapshot({ series: [], items });
    expect(snap.tierSummary.tier).not.toBe('Unranked');
  });

  it('scores rarity and completeness above zero', () => {
    const snap = computePortfolioSnapshot({ series: [], items });
    expect(snap.tierSummary.rarityScore).toBeGreaterThan(0);
    expect(snap.tierSummary.completenessScore).toBeGreaterThan(0);
  });

  it('reports how many items the rarity average is built from', () => {
    const snap = computePortfolioSnapshot({ series: [], items });
    expect(snap.tierSummary.rarityCoverage).toEqual({ known: 4, total: 4 });
  });
});

describe('unknowns are excluded, never counted as zero', () => {
  it('averages rarity over the items that have one', () => {
    const snap = computePortfolioSnapshot({
      series: [],
      items: [
        item({ rarityScore: 0.9, raritySource: 'catalog' }),
        item({}), // no rarity: unreadable attributes
        item({}),
      ],
    });
    // 0.9, not 0.9/3 — an unreadable item must not drag the average down.
    expect(snap.tierSummary.rarityScore).toBeCloseTo(0.9, 5);
    expect(snap.tierSummary.rarityCoverage).toEqual({ known: 1, total: 3 });
  });

  it('a set with no catalogue row is skipped, not treated as 0% complete', () => {
    const withUnknownSet = computePortfolioSnapshot({
      series: [],
      items: [
        item({ collection: 'Known', setSize: 2, rarityScore: 0.9 }),
        item({ collection: 'Uncatalogued', setSize: null, rarityScore: 0.9 }),
      ],
    });
    const knownOnly = computePortfolioSnapshot({
      series: [],
      items: [item({ collection: 'Known', setSize: 2, rarityScore: 0.9 })],
    });
    expect(withUnknownSet.tierSummary.completenessScore).toBeCloseTo(
      knownOnly.tierSummary.completenessScore,
      5,
    );
  });

  it('a genuinely empty collection still reports Unranked with 0 coverage', () => {
    const snap = computePortfolioSnapshot({ series: [], items: [] });
    expect(snap.tierSummary.tier).toBe('Unranked');
    expect(snap.tierSummary.rarityCoverage).toEqual({ known: 0, total: 0 });
  });
});
