/** Steps drive a project's progress (2026-09-25: 3/12 done still read 0%). */
import { stepsProgressPercent } from '@/lib/projectProgress';

describe('stepsProgressPercent', () => {
  const steps = (done: number, total: number) => Array.from({ length: total }, (_, i) => ({ isDone: i < done }));
  it('3 of 12 is 25%', () => expect(stepsProgressPercent(steps(3, 12))).toBe(25));
  it('all done is 100%', () => expect(stepsProgressPercent(steps(12, 12))).toBe(100));
  it('none is 0%, and no steps is 0%', () => {
    expect(stepsProgressPercent(steps(0, 12))).toBe(0);
    expect(stepsProgressPercent([])).toBe(0);
  });
});
