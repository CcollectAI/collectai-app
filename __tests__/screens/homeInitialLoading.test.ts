/**
 * Home's `loading` must start TRUE.
 *
 * WHY THIS TEST EXISTS (2026-09-14, Android walk): the first portfolio load
 * waits for auth to hydrate, which takes seconds on a cold start. `loading`
 * started `false`, so that window looked like a finished, empty load — an
 * account holding €1.348 opened on "COLLECTION VALUE €0 / +€0 (0.00%)" and
 * "No history yet. Add items to see your portfolio curve." The header's null
 * guard (`series.length === 0 && (loading || seriesFailed)`) was correct; it
 * was fed a state that said "done" before anything had started.
 *
 * Static on purpose: mounting Home needs dozens of providers, and the defect
 * is one literal. Same shape as __tests__/data/noDirectEventViewRead.test.ts.
 */
import { readFileSync } from 'fs';
import { join } from 'path';

const HOME = readFileSync(join(__dirname, '../../app/(tabs)/index.tsx'), 'utf8');

describe('Home initial loading state', () => {
  it('declares the portfolio loading flag as true until the first load settles', () => {
    const decl = HOME.match(/const \[loading, setLoading\] = useState(?:<boolean>)?\((true|false)\)/);
    expect(decl).not.toBeNull();
    expect(decl![1]).toBe('true');
  });

  it('still gates the first load on auth — the reason the flag must start true', () => {
    expect(HOME).toMatch(/if \(authLoading\) return;\s*loadData\(\);/);
  });
});
