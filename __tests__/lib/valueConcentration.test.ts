/**
 * The allocation card's concentration verdict must name the category that holds
 * the most VALUE — the one the bar above it shows first — not the one with the
 * most items. It named the wrong one on 2026-09-22 (see valueConcentration).
 */
import { valueConcentration } from '@/lib/portfolioAnalytics';

describe('valueConcentration', () => {
  it('names the category with the most VALUE, not the most items (the walked case)', () => {
    // The test account: 4 Pokémon items worth 17.64%, 1 LEGO item worth 66.78%.
    const allocations = [
      { category: 'pokemon', weight: 0.1764 },
      { category: 'lego', weight: 0.6678 },
      { category: 'lorcana', weight: 0.089 },
      { category: 'yugioh', weight: 0.0445 },
      { category: 'one_piece_tcg', weight: 0.0223 },
    ];
    expect(valueConcentration(allocations)).toEqual({ category: 'lego', level: 'high' });
  });

  it('is medium between 0.40 and 0.50, matching the server thresholds', () => {
    expect(valueConcentration([
      { category: 'a', weight: 0.45 }, { category: 'b', weight: 0.35 }, { category: 'c', weight: 0.2 },
    ])).toEqual({ category: 'a', level: 'medium' });
    expect(valueConcentration([
      { category: 'a', weight: 0.4 }, { category: 'b', weight: 0.6 - 0.0001 },
    ])?.level).toBe('high');
  });

  it('says nothing below 0.40', () => {
    expect(valueConcentration([
      { category: 'a', weight: 0.39 }, { category: 'b', weight: 0.31 }, { category: 'c', weight: 0.3 },
    ])).toBeNull();
  });

  it('says nothing for a single category or no data', () => {
    expect(valueConcentration([{ category: 'a', weight: 1 }])).toBeNull();
    expect(valueConcentration([])).toBeNull();
  });
});
