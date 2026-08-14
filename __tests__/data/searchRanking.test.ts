/**
 * Search ranking by followed categories.
 *
 * The two properties that matter are both about what ranking must NOT do:
 * it must not hide anything, and it must not disturb the server's relevance
 * order inside a group. A partition that quietly drops a row, or that reverses
 * two equally-followed results, would be invisible on screen and would only
 * ever be reported as "search feels wrong".
 */
import {
  partitionByFollowed,
  partitionCategoriesByFollowed,
  rankSearchResults,
} from '@/data/searchRanking';

const rows = [
  { id: 'a', category: 'warhammer' },
  { id: 'b', category: 'pokemon' },
  { id: 'c', category: 'mtg' },
  { id: 'd', category: 'pokemon' },
  { id: 'e', category: null },
];

describe('partitionByFollowed', () => {
  it('puts followed categories first', () => {
    const out = partitionByFollowed(rows, new Set(['pokemon']));
    expect(out.map((r) => r.id)).toEqual(['b', 'd', 'a', 'c', 'e']);
  });

  it('LOSES NOTHING — ranking is not filtering', () => {
    const out = partitionByFollowed(rows, new Set(['pokemon']));
    expect(out).toHaveLength(rows.length);
    expect(new Set(out.map((r) => r.id))).toEqual(new Set(rows.map((r) => r.id)));
  });

  it('preserves the server order inside each half', () => {
    // b before d (both followed), a before c before e (both not) — exactly the
    // order they arrived in. The server already ranked by relevance and this
    // must only partition it.
    const out = partitionByFollowed(rows, new Set(['pokemon']));
    expect(out.map((r) => r.id).slice(0, 2)).toEqual(['b', 'd']);
    expect(out.map((r) => r.id).slice(2)).toEqual(['a', 'c', 'e']);
  });

  it('is a no-op with no follows', () => {
    expect(partitionByFollowed(rows, new Set()).map((r) => r.id)).toEqual(
      rows.map((r) => r.id),
    );
  });

  it('handles a null category without treating it as followed', () => {
    const out = partitionByFollowed(rows, new Set(['pokemon']));
    expect(out[out.length - 1].id).toBe('e');
  });
});

describe('partitionCategoriesByFollowed', () => {
  it('keys on id, because the category list has no `category` field', () => {
    const cats = [{ id: 'mtg' }, { id: 'pokemon' }, { id: 'lego' }];
    expect(
      partitionCategoriesByFollowed(cats, new Set(['pokemon'])).map((c) => c.id),
    ).toEqual(['pokemon', 'mtg', 'lego']);
  });
});

describe('rankSearchResults', () => {
  const results = {
    items: [{ category: 'mtg' }, { category: 'pokemon' }],
    catalog: [{ category: 'mtg' }, { category: 'pokemon' }],
    events: [{ category: 'mtg' }, { category: 'pokemon' }],
    categories: [{ id: 'mtg' }, { id: 'pokemon' }],
    users: [{ id: 'u1' }, { id: 'u2' }],
  };

  it('ranks every categorised list', () => {
    const out = rankSearchResults(results, new Set(['pokemon']))!;
    expect(out.items[0].category).toBe('pokemon');
    expect(out.catalog[0].category).toBe('pokemon');
    expect(out.events[0].category).toBe('pokemon');
    expect(out.categories[0].id).toBe('pokemon');
  });

  it('leaves users untouched — a person has no category to rank by', () => {
    const out = rankSearchResults(results, new Set(['pokemon']))!;
    expect(out.users).toEqual(results.users);
  });

  it('returns the SAME object when there is nothing to do', () => {
    // Identity matters: a caller memoising on it must not re-render for a no-op.
    expect(rankSearchResults(results, new Set())).toBe(results);
    expect(rankSearchResults(null, new Set(['pokemon']))).toBeNull();
  });
});

describe('the category accessor', () => {
  it('reads a differently-named field without copying rows', () => {
    // Events carry `categoryId`, not `category`. The caller used to bridge that
    // with {...e, category: e.categoryId} — one new object per event, to rename
    // one field, leaving a property the Event type never declared.
    const events = [
      { id: 'e1', categoryId: 'mtg' },
      { id: 'e2', categoryId: 'pokemon' },
    ];
    const out = partitionByFollowed(events, new Set(['pokemon']), (e) => e.categoryId);
    expect(out.map((e) => e.id)).toEqual(['e2', 'e1']);
    // Identity preserved: the same objects come back, not copies.
    expect(out[0]).toBe(events[1]);
    expect(out[1]).toBe(events[0]);
  });
});
