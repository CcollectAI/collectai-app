/**
 * The item card's attribute rows: what gets shown, what gets hidden, and what
 * gets renamed so no label appears twice.
 *
 * Every rule pinned here shipped WITHOUT a test, inside a component that could
 * only be exercised by rendering it — so each was verified by re-reading it,
 * which `feedback_audit_my_diff_with_a_checker_not_a_reread` says catches
 * roughly nothing. The row-building was extracted to a pure function
 * (2026-08-23) for exactly this file.
 *
 * The fixtures are REAL prod shapes, not invented ones. That distinction has
 * already cost once: an invented fixture for the label dedupe had one empty
 * side, so it could not show that the first version silently deleted the
 * populated one (CLAUDE.md, "A label dedupe that silently deleted data").
 */
import {
  buildAttributeRows,
  flattenAttributes,
} from '@/components/ItemAttributesSection';

/** Labels `ItemDetailsCard` renders itself for a grading-eligible category. */
const RESERVED = ['Category', 'Collection', 'Grade'];

const labelsOf = (rows: [string, unknown, string][]) => rows.map(([, , l]) => l);
const rowFor = (rows: [string, unknown, string][], key: string) =>
  rows.find(([k]) => k === key);

describe('internal bookkeeping keys never render as rows', () => {
  // The exact keys present in prod `attrs`, 2026-08-23. All 22 were read
  // before the blocklist was drawn, per
  // learning_keyword_filters_need_per_category_false_positive_audit.
  const attrs = {
    brand: 'Bunnahabhain',
    value_choice: 'mine',
    intake_timestamp: '2026-07-26T21:32:30.736662+00:00',
    source: 'open_library',
    item_type: 'Merch',
    sealed: 'false',
  };

  it('hides value_choice, intake_timestamp and source', () => {
    const rows = buildAttributeRows({ attrs, category: 'whiskey' });
    expect(rowFor(rows, 'value_choice')).toBeUndefined();
    expect(rowFor(rows, 'intake_timestamp')).toBeUndefined();
    expect(rowFor(rows, 'source')).toBeUndefined();
  });

  it('KEEPS item_type and sealed — they are facts, not plumbing', () => {
    // The half that makes the blocklist a measurement rather than a guess: two
    // of the five suspicious-looking keys carry real values.
    const rows = buildAttributeRows({ attrs, category: 'whiskey' });
    expect(rowFor(rows, 'item_type')?.[1]).toBe('Merch');
    expect(rowFor(rows, 'sealed')?.[1]).toBe('false');
  });

  it('hides value_choice in EDIT mode too', () => {
    // The blocklist must not be read-mode-only the way the brand suppression
    // deliberately is: `value_choice` is not a field anyone should correct by
    // hand, and edit mode is where the comp prompt's answer would surface.
    const rows = buildAttributeRows({ attrs, category: 'whiskey', editable: true });
    expect(rowFor(rows, 'value_choice')).toBeUndefined();
  });
});

describe("the parent's labels are reserved", () => {
  it('drops an EMPTY attribute whose label the card already renders', () => {
    // The reported defect: "Grade" twice, four rows apart. In edit mode the
    // yugioh field list synthesises an empty `grade`, and the card renders the
    // real one from `items.condition`.
    const rows = buildAttributeRows({
      attrs: { rarity: 'Ultra Rare' },
      category: 'yugioh',
      editable: true,
      reservedLabels: RESERVED,
    });
    expect(labelsOf(rows).filter((l) => l === 'Grade')).toHaveLength(0);
    expect(labelsOf(rows)).toContain('Rarity');
  });

  it('KEEPS a filled one and disambiguates it rather than hiding data', () => {
    // `attrs.grade` is on zero prod rows today, which is exactly why this
    // branch needs a test: the day one appears, suppressing it would hide a
    // real captured value behind the card's "Not set".
    const rows = buildAttributeRows({
      attrs: { grade: 'PSA 10' },
      category: 'yugioh',
      editable: true,
      reservedLabels: RESERVED,
    });
    const grade = rowFor(rows, 'grade');
    expect(grade?.[1]).toBe('PSA 10');
    expect(grade?.[2]).toBe('Grade (captured)');
    expect(labelsOf(rows).filter((l) => l === 'Grade')).toHaveLength(0);
  });

  it('is a no-op when the parent declares nothing', () => {
    const rows = buildAttributeRows({
      attrs: { grade: 'PSA 10' },
      category: 'yugioh',
    });
    expect(rowFor(rows, 'grade')?.[2]).toBe('Grade');
  });

  it('the empty Grade row IS present without the reservation', () => {
    // The discriminator. Without this, the "drops an EMPTY attribute" test
    // above passes for any reason at all — including a `grade` row that was
    // never synthesised in the first place, which would make the rule a
    // no-op wearing a green tick. Same inputs, `reservedLabels` omitted: the
    // duplicate the screenshot showed must come back.
    const rows = buildAttributeRows({
      attrs: { rarity: 'Ultra Rare' },
      category: 'yugioh',
      editable: true,
    });
    expect(labelsOf(rows)).toContain('Grade');
  });
});

describe('one label, one row', () => {
  it('drops the EMPTY duplicate when two keys share a label', () => {
    // `set_name` (catalogue) and `set` (yugioh field list) both label as "Set".
    const rows = buildAttributeRows({
      attrs: { set_name: 'BLAR', set: '' },
      category: 'yugioh',
      editable: true,
    });
    expect(labelsOf(rows).filter((l) => l === 'Set')).toHaveLength(1);
    expect(rowFor(rows, 'set_name')?.[1]).toBe('BLAR');
  });

  it('keeps BOTH when both carry data, and never shows one label twice', () => {
    // The real corrupted prod row: set_name "BLAR" beside set "jdhd".
    // Collapsing them discarded what the member typed.
    const rows = buildAttributeRows({
      attrs: { set_name: 'BLAR', set: 'jdhd' },
      category: 'yugioh',
      editable: true,
    });
    const values = rows.filter(([k]) => k === 'set' || k === 'set_name').map(([, v]) => v);
    expect(values).toContain('BLAR');
    expect(values).toContain('jdhd');
    const labels = labelsOf(rows);
    expect(new Set(labels).size).toBe(labels.length); // no label appears twice
  });
});

describe('a brand that only restates the category', () => {
  it('is suppressed in read mode', () => {
    const rows = buildAttributeRows({
      attrs: { brand: 'Yu-Gi-Oh' }, // prod stores this; display name is 'Yu-Gi-Oh!'
      category: 'yugioh',
    });
    expect(rowFor(rows, 'brand')).toBeUndefined();
  });

  it('folds diacritics rather than stripping them', () => {
    // The audit catch: `[^a-z0-9]` alone turns 'Pokémon' into 'pokmon' while a
    // stored 'Pokemon' becomes 'pokemon', so the app's LARGEST category could
    // never match and would keep the row this exists to remove.
    const rows = buildAttributeRows({
      attrs: { brand: 'Pokemon' },
      category: 'pokemon',
    });
    expect(rowFor(rows, 'brand')).toBeUndefined();
  });

  it('KEEPS a real brand that is not the category', () => {
    const rows = buildAttributeRows({
      attrs: { brand: 'Bunnahabhain' },
      category: 'whiskey',
    });
    expect(rowFor(rows, 'brand')?.[1]).toBe('Bunnahabhain');
  });

  it('stays visible in EDIT mode so a wrong value can be corrected', () => {
    const rows = buildAttributeRows({
      attrs: { brand: 'Yu-Gi-Oh' },
      category: 'yugioh',
      editable: true,
    });
    expect(rowFor(rows, 'brand')?.[1]).toBe('Yu-Gi-Oh');
  });
});

describe('flattening a double-encoded attrs array', () => {
  // The literal prod value that rendered raw JSON with "0" and "1" as labels.
  const CORRUPTED = [
    { brand: 'Pokemon TCG', rarity: 'Rare Holo', set_code: 'gym1' },
    '{"set_code": ""}',
    '{"value_choice": "mine"}',
  ];

  it('collapses to one object without letting an empty overwrite a real value', () => {
    const flat = flattenAttributes(CORRUPTED);
    expect(flat?.set_code).toBe('gym1'); // NOT '' from the later element
    expect(flat?.rarity).toBe('Rare Holo');
  });

  it('renders as ordinary rows, not as JSON under numeric labels', () => {
    const rows = buildAttributeRows({
      attrs: flattenAttributes(CORRUPTED),
      category: 'pokemon',
    });
    expect(labelsOf(rows)).not.toContain('0');
    expect(labelsOf(rows)).not.toContain('1');
    expect(rowFor(rows, 'set_code')?.[1]).toBe('gym1');
    // and the bookkeeping key that rode in on the corruption stays hidden
    expect(rowFor(rows, 'value_choice')).toBeUndefined();
  });

  it('returns null for a value that is not an attribute bag', () => {
    expect(flattenAttributes(null)).toBeNull();
    expect(flattenAttributes('not json')).toBeNull();
    expect(flattenAttributes(['not json either'])).toBeNull();
  });
});
