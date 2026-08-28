import { buildAttributeRows } from '@/components/ItemAttributesSection';

const labels = (rows: [string, unknown, string][]) => rows.map((r) => r[2]);

/**
 * "Sealed: No" on a graded single, reported 2026-08-28.
 *
 * The attrs below are the REAL row for the seeded PSA 9 Rayquaza, copied out of
 * prod, not invented.
 */
describe('undeclared false booleans are not facts', () => {
  const RAYQUAZA = {
    number: '097', rarity: 'Ultra Rare', sealed: false,
    set_code: 'ex6', item_type: 'Single',
  };

  it('drops "Sealed: No" on a pokemon single, whose category never declares sealed', () => {
    const rows = buildAttributeRows({ attrs: RAYQUAZA, category: 'pokemon' });
    expect(labels(rows)).not.toContain('Sealed');
    // The real attributes are untouched — this must not empty the card.
    expect(labels(rows)).toEqual(expect.arrayContaining(['Card Number', 'Rarity']));
  });

  it('KEEPS "Sealed: No" where the category declares it — loose vs MISB is real', () => {
    const rows = buildAttributeRows({ attrs: { sealed: false }, category: 'lego' });
    // LEGO_FIELDS labels it "Sealed / New in Box" — asserted on the DECLARED
    // label rather than the bare key, because the label is the category's own
    // wording and pinning "Sealed" here would pass for the wrong reason.
    expect(labels(rows)).toContain('Sealed / New in Box');
  });

  it('keeps sealed:true everywhere — a sealed box is never noise', () => {
    expect(labels(buildAttributeRows({ attrs: { sealed: true }, category: 'pokemon' })))
      .toContain('Sealed');
  });

  it('keeps the row in EDIT mode so a wrong value stays correctable', () => {
    const rows = buildAttributeRows({ attrs: RAYQUAZA, category: 'pokemon', editable: true });
    expect(labels(rows)).toContain('Sealed');
  });

  it('does not drop other falsy-looking values that are real data', () => {
    const rows = buildAttributeRows({ attrs: { number: '0', rarity: 'Common' }, category: 'pokemon' });
    expect(labels(rows)).toEqual(expect.arrayContaining(['Card Number', 'Rarity']));
  });
});

describe('the rule fails toward showing, never toward hiding', () => {
  it('keeps a false boolean when the category is unknown', () => {
    // No category means no declared vocabulary to judge against. Same direction
    // the diacritic-fold guard in this file fails in: a redundant row beats a
    // hidden fact.
    const rows = buildAttributeRows({ attrs: { sealed: false } });
    expect(rows.map((r) => r[2])).toContain('Sealed');
  });

  it('does not touch a STRINGIFIED false, which is captured data', () => {
    const rows = buildAttributeRows({ attrs: { sealed: 'false' }, category: 'pokemon' });
    expect(rows.find((r) => r[0] === 'sealed')?.[1]).toBe('false');
  });
});
