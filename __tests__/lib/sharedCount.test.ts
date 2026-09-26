import { createSharedCount } from '@/lib/sharedCount';

// set() exists because the bell kept its cached count through a mark-read
// (2026-09-26: badge stayed at 13). It must win over a fetch already in flight,
// which carries the count from before the change.
describe('createSharedCount.set', () => {
  it('takes the known value, stamps it fresh, and notifies listeners', async () => {
    const fetcher = jest.fn().mockResolvedValue(13);
    const c = createSharedCount(fetcher, 60_000);
    await c.refreshIfStale('u1');
    const seen: number[] = [];
    c.subscribe((v) => seen.push(v));
    c.set('u1', 12);
    expect(c.peek('u1')).toBe(12);
    expect(seen).toEqual([12]);
    await c.refreshIfStale('u1'); // fresh → no refetch
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('drops the answer of a request that started before set()', async () => {
    let resolve!: (n: number) => void;
    const c = createSharedCount(() => new Promise<number>((r) => { resolve = r; }), 60_000);
    const pending = c.refreshIfStale('u1');
    c.set('u1', 4);
    resolve(13);
    await pending;
    expect(c.peek('u1')).toBe(4);
  });

  it('does not hand one account the count of another', () => {
    const c = createSharedCount(jest.fn().mockResolvedValue(0), 60_000);
    c.set('u1', 5);
    expect(c.peek('u2')).toBe(0);
  });
});
