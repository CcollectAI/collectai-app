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
  humaniseInsight,
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
  it('says each concentration fact ONCE — the exposure adopts its suggestion', () => {
    // This test used to assert 4 notes and pin the bug. On screen that read:
    //   "pokemon is 82% of your collection."
    //   "Your entire portfolio is in 'pokemon'. Consider diversifying..."
    // — one fact, printed twice, back to back.
    const notes = mapRiskNotes(makeRaw());
    expect(notes).toHaveLength(2);

    const texts = notes.map((n) => n.text);
    // The server sentence survives (it carries the action); ours does not.
    expect(texts.some((t) => t.includes('Consider diversifying'))).toBe(true);
    expect(texts.some((t) => /^pokemon is 82%/.test(t))).toBe(false);
  });

  it('keeps the exposure LEVEL when it adopts a suggestion', () => {
    // The reason this merges instead of dropping our half: every suggestion is
    // `info`, so discarding the exposure would demote a HIGH concentration
    // warning to a grey line and lose sharePct with it.
    const notes = mapRiskNotes(makeRaw());
    const pokemon = notes.find((n) => n.category === 'pokemon')!;
    expect(pokemon.level).toBe('high');
    expect(pokemon.sharePct).toBe(0.82);
  });

  it('prints display names, never raw slugs', () => {
    const notes = mapRiskNotes({
      overexposed_categories: [{ category: 'lorcana', share_pct: 0.4, risk_level: 'high' }],
    });
    expect(notes[0].text).toBe('Disney Lorcana is 40% of your collection.');
    expect(notes[0].text).not.toMatch(/lorcana/);
  });

  it('an unmatched suggestion is still shown', () => {
    const notes = mapRiskNotes(
      makeRaw({ diversification_suggestions: ['Spread out a bit.'] }),
    );
    // 2 exposures, neither named by the suggestion, plus the suggestion itself.
    expect(notes).toHaveLength(3);
    expect(notes.map((n) => n.text)).toContain('Spread out a bit.');
  });

  it('does not let two exposures claim the same sentence', () => {
    // 'pokemon' and 'pokemon_cards' both substring-match a sentence about
    // pokemon. Without claiming, both would adopt it and the SAME text would
    // render twice — the exact bug this fix exists to remove.
    const notes = mapRiskNotes({
      overexposed_categories: [
        { category: 'pokemon', share_pct: 0.5, risk_level: 'high' },
        { category: 'pokemon_cards', share_pct: 0.3, risk_level: 'medium' },
      ],
      diversification_suggestions: ["Your entire portfolio is in 'pokemon'."],
    });
    expect(new Set(notes.map((n) => n.text)).size).toBe(notes.length);
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
    // The suggestion names no category, so it stays a standalone info note.
    expect(notes[2].text).toBe('Spread out a bit.');
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

describe('humaniseInsight — backend f-string artefacts', () => {
  it('replaces a quoted slug with the display name', () => {
    expect(humaniseInsight("Your 'lorcana' exposure is 40% of your portfolio.")).toBe(
      'Your Disney Lorcana exposure is 40% of your portfolio.',
    );
  });

  it('turns a double hyphen into an em dash', () => {
    expect(humaniseInsight('Grow it -- it is your smallest.')).toBe(
      'Grow it \u2014 it is your smallest.',
    );
  });

  it('leaves ordinary quoted prose alone', () => {
    // 'value' is not a category. Rewriting it to "Value" would be the mapper
    // inventing emphasis the backend never wrote.
    expect(humaniseInsight("Watch the 'value' column.")).toBe("Watch the 'value' column.");
  });

  it('does not mangle an apostrophe in ordinary text', () => {
    expect(humaniseInsight("A collector's set, don't sell it.")).toBe(
      "A collector's set, don't sell it.",
    );
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
