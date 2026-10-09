import { readFileSync } from 'fs';
import { join } from 'path';

/**
 * The Items list rows must not be wrapped in the stagger reveal (2026-10-09).
 *
 * On Android (release APK, SparrowWalk emulator, Animations ON) the list view
 * drew every category header and total with EVERY item row invisible — absent
 * even from a uiautomator dump — after both iOS fixes in useStaggerReveal had
 * shipped. Settings → Animations OFF made every row appear; that path is "the
 * row gets no stagger style", which items.tsx now always takes. The hook itself
 * still animates the leaderboard rows fine on the same device, so the failure
 * is this list's combination, not the hook — and a test of the hook (see
 * staggerRevealGrowth.test.ts) cannot see it. This one reads the screen.
 */
describe('Items list rows — no stagger reveal', () => {
  const src = readFileSync(join(__dirname, '../../app/(tabs)/items.tsx'), 'utf8');
  // Comments explain the history and name the hook; only code counts.
  const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');

  it('does not use useStaggerReveal', () => {
    expect(code).not.toMatch(/useStaggerReveal/);
  });

  it('does not pass a staggerStyle to ItemsListItem', () => {
    expect(code).not.toMatch(/staggerStyle\s*=/);
  });
});
