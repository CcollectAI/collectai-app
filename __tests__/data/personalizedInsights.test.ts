/**
 * /insights/personalized → screen pass-through gate.
 *
 * The backend computes four arrays; the marketplace screen used to cast the
 * response inline to `{ trending_items?: ... }`, so `overexposed_categories`,
 * `diversification_suggestions` and `rare_set_alerts` were discarded at the
 * type boundary and never rendered. tsc cannot catch that — a narrowing cast
 * is legal — and no component test exercised the mapping. These assertions pin
 * the fields so a future edit can't silently drop them again.
 *
 * Backend contract: server/app/features/insights_router.py:32-54.
 */
import {
  mapRiskNotes,
  mapTrendingCategories,
  type RawPersonalizedInsights,
} from '../../src/data/personalizedInsights';

function makeRaw(overrides: Partial<RawPersonalizedInsights> = {}): RawPersonalizedInsights {
  return {
    overexposed_categories: [
      { category: 'pokemon', share_pct: 0.82, risk_level: 'high' },
      { category: 'funko', share_pct: 0.12, risk_level: 'medium' },
    ],
    diversification_suggestions: [
      "Your entire portfolio is in 'pokemon'. Consider diversifying into other categories to reduce risk.",
      "Consider growing your 'funko' collection -- it is currently your smallest category.",
    ],
    rare_set_alerts: [
      { category: 'pokemon', item_name: 'Base Set', note: 'You own 8/10 (80%). Only 2 items to complete!' },
    ],
    trending_items: [
      { category: 'pokemon', item_name: 'Charizard', change_pct: 0.21 },
      { category: 'funko', item_name: 'Batman', change_pct: -0.05 },
    ],
    ...overrides,
  };
}

describe('mapRiskNotes — concentration + diversification pass-through', () => {
  it('surfaces every overexposed category and every suggestion', () => {
    const notes = mapRiskNotes(makeRaw());
    // 2 exposures + 2 suggestions must all reach the screen.
    expect(notes).toHaveLength(4);

    const texts = notes.map((n) => n.text);
    expect(texts.some((t) => t.includes('pokemon') && t.includes('82%'))).toBe(true);
    expect(texts).toContain(
      "Your entire portfolio is in 'pokemon'. Consider diversifying into other categories to reduce risk.",
    );
    expect(texts).toContain(
      "Consider growing your 'funko' collection -- it is currently your smallest category.",
    );
  });

  it('treats share_pct as a fraction, not an already-multiplied percentage', () => {
    const notes = mapRiskNotes(
      makeRaw({ overexposed_categories: [{ category: 'mtg', share_pct: 0.42, risk_level: 'high' }] }),
    );
    expect(notes[0].sharePct).toBe(0.42);
    expect(notes[0].text).toContain('42%');
    expect(notes[0].text).not.toContain('0%');
  });

  it('orders high risk before medium before informational suggestions', () => {
    const notes = mapRiskNotes(
      makeRaw({
        overexposed_categories: [
          { category: 'funko', share_pct: 0.2, risk_level: 'medium' },
          { category: 'pokemon', share_pct: 0.8, risk_level: 'high' },
        ],
        diversification_suggestions: ['Spread out a bit.'],
      }),
    );
    expect(notes.map((n) => n.level)).toEqual(['high', 'medium', 'info']);
    expect(notes[0].category).toBe('pokemon');
  });

  it('survives nulls, empties and a missing payload without throwing', () => {
    expect(mapRiskNotes(null)).toEqual([]);
    expect(mapRiskNotes(undefined)).toEqual([]);
    expect(mapRiskNotes({})).toEqual([]);
    expect(
      mapRiskNotes({
        overexposed_categories: [{ category: null, share_pct: null, risk_level: null }],
        diversification_suggestions: [null, '  ', 'Real tip.'],
      }),
    ).toEqual([{ id: 'suggestion:0', level: 'info', text: 'Real tip.' }]);
  });

  it('renders a category with no share_pct without printing NaN', () => {
    const notes = mapRiskNotes({ overexposed_categories: [{ category: 'lego', risk_level: 'high' }] });
    expect(notes[0].text).not.toMatch(/NaN/);
    expect(notes[0].sharePct).toBeUndefined();
  });

  it('produces unique keys so the list can render without collisions', () => {
    const notes = mapRiskNotes(makeRaw());
    expect(new Set(notes.map((n) => n.id)).size).toBe(notes.length);
  });
});

describe('mapTrendingCategories — unchanged rail behaviour', () => {
  const names = { pokemon: 'Pokémon', funko: 'Funko Pop' };

  it('maps categories, applies display names and dedupes', () => {
    const rail = mapTrendingCategories(makeRaw(), names);
    expect(rail).toEqual([
      { id: 'pokemon', name: 'Pokémon', meta: '+21% this month' },
      { id: 'funko', name: 'Funko Pop', meta: 'Popular' },
    ]);
  });

  it('drops duplicates and entries with no category', () => {
    const rail = mapTrendingCategories(
      {
        trending_items: [
          { category: 'pokemon', change_pct: 0.5 },
          { category: 'pokemon', change_pct: 0.1 },
          { category: null, change_pct: 0.9 },
        ],
      },
      names,
    );
    expect(rail).toHaveLength(1);
  });

  it('falls back to the raw slug when no display name exists', () => {
    const rail = mapTrendingCategories({ trending_items: [{ category: 'obscure', change_pct: 0.3 }] }, names);
    expect(rail[0].name).toBe('obscure');
  });

  it('survives a missing payload', () => {
    expect(mapTrendingCategories(null, names)).toEqual([]);
    expect(mapTrendingCategories({}, names)).toEqual([]);
  });
});
