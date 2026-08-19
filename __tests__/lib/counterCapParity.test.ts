/**
 * The counter cap exists in TWO languages, and only one of them enforces it.
 *
 * `app/offers.tsx` hides the Counter button at `MAX_COUNTERS`; the server
 * refuses with 409 `COUNTER_LIMIT`. If they drift, the failure is asymmetric
 * and both directions are bad:
 *
 *  - FE higher than BE → a button whose only outcome is an error toast. That
 *    is the dead-button failure Stage 1 bug 0 was fixed to avoid.
 *  - FE lower than BE  → a control silently removed while the server would
 *    still have accepted it, which nobody can report because there is nothing
 *    to point at.
 *
 * A comment saying "must match" is not a gate — this is
 * `learning_billing_limits_fe_be_contract` in miniature, and the same shape as
 * `check-billing-limits-parity.mjs`.
 */
import { readFileSync } from 'fs';
import { join } from 'path';

const ROOT = join(__dirname, '..', '..');

function constantFrom(relPath: string, pattern: RegExp): number {
  const src = readFileSync(join(ROOT, relPath), 'utf8');
  const m = src.match(pattern);
  if (!m) throw new Error(`no cap constant found in ${relPath} — it was renamed or deleted`);
  return Number(m[1]);
}

describe('counter cap parity', () => {
  const fe = () => constantFrom('app/offers.tsx', /^const MAX_COUNTERS = (\d+);/m);
  const be = () => constantFrom(
    'server/app/features/p2p_offers_router.py', /^MAX_COUNTERS = (\d+)$/m);

  it('the client hides the button at the same number the server refuses at', () => {
    expect(fe()).toBe(be());
  });

  it('the cap is a real number, not a placeholder', () => {
    // A 0 would remove countering entirely and a 1 would end a haggle before
    // it started; both would pass a bare equality check.
    expect(fe()).toBeGreaterThan(1);
  });

  it('the server actually enforces it, rather than only defining it', () => {
    const src = readFileSync(
      join(ROOT, 'server/app/features/p2p_offers_router.py'), 'utf8');
    expect(src).toContain('code="COUNTER_LIMIT"');
    expect(src).toMatch(/counter_count.*\]\s*or 0\)\s*>=\s*MAX_COUNTERS/);
  });
});
