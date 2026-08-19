/**
 * Competing bids must end up next to each other WITHOUT breaking the priority
 * order the sections encode.
 *
 * The gap is documented in docs/P2P_MARKETPLACE_SPEC.md: two bids on the same
 * item could sit ten cards apart. The risk in fixing it is the opposite error —
 * letting a listing group outrank "needs you", so a member's own move sinks
 * below a listing nobody is asking them about.
 */
import { groupCompetingOffers } from '@/lib/offerGrouping';

const o = (id: string, listing_id: string, amount: number) => ({ id, listing_id, amount });

describe('groupCompetingOffers', () => {
  it('leaves a list of single-listing offers exactly as it found it', () => {
    const input = [o('a', 'L1', 10), o('b', 'L2', 20), o('c', 'L3', 30)];
    const { ordered, meta } = groupCompetingOffers(input);
    expect(ordered.map((x) => x.id)).toEqual(['a', 'b', 'c']);
    expect([...meta.values()].every((m) => m.size === 1)).toBe(true);
  });

  it('pulls competing bids together', () => {
    // b and d compete; c is unrelated and must not be dragged along.
    const input = [o('a', 'L1', 10), o('b', 'L2', 20), o('c', 'L3', 30), o('d', 'L2', 45)];
    const { ordered } = groupCompetingOffers(input);
    expect(ordered.map((x) => x.id)).toEqual(['a', 'd', 'b', 'c']);
  });

  it('puts the HIGHEST bid first inside a group', () => {
    const input = [o('low', 'L1', 5), o('high', 'L1', 50), o('mid', 'L1', 25)];
    expect(groupCompetingOffers(input).ordered.map((x) => x.id))
      .toEqual(['high', 'mid', 'low']);
  });

  it('keeps the group where its FIRST member already ranked', () => {
    // The section is already sorted by priority. If the group jumped to the
    // position of its highest bid, a needs-you card could sink below one that
    // does not need you at all.
    const input = [o('urgent', 'L9', 1), o('x', 'L1', 10), o('y', 'L1', 999)];
    const { ordered } = groupCompetingOffers(input);
    expect(ordered[0].id).toBe('urgent');
    expect(ordered.map((x) => x.id)).toEqual(['urgent', 'y', 'x']);
  });

  it('marks only the first card of a group as the header', () => {
    const { meta } = groupCompetingOffers([o('a', 'L1', 10), o('b', 'L1', 20)]);
    const firsts = [...meta.values()].filter((m) => m.isFirst);
    expect(firsts).toHaveLength(1);
    // A single-offer listing draws no header at all.
    const { meta: solo } = groupCompetingOffers([o('a', 'L1', 10)]);
    expect([...solo.values()][0].isFirst).toBe(false);
  });

  it('reports the spread a seller is choosing across', () => {
    const { meta } = groupCompetingOffers([o('a', 'L1', 28), o('b', 'L1', 41), o('c', 'L1', 33)]);
    const m = meta.get('b')!;
    expect(m).toMatchObject({ size: 3, low: 28, high: 41, isFirst: true });
  });

  it('never drops or duplicates an offer', () => {
    const input = [o('a', 'L1', 1), o('b', 'L2', 2), o('c', 'L1', 3), o('d', 'L3', 4), o('e', 'L2', 5)];
    const { ordered, meta } = groupCompetingOffers(input);
    expect(ordered).toHaveLength(input.length);
    expect(new Set(ordered.map((x) => x.id)).size).toBe(input.length);
    expect(meta.size).toBe(input.length);
  });

  it('does not mutate the input', () => {
    const input = [o('a', 'L1', 1), o('b', 'L1', 9)];
    const copy = input.map((x) => ({ ...x }));
    groupCompetingOffers(input);
    expect(input).toEqual(copy);
  });

  it('handles an empty list', () => {
    const { ordered, meta } = groupCompetingOffers([]);
    expect(ordered).toEqual([]);
    expect(meta.size).toBe(0);
  });
});
