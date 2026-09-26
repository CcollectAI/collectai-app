/**
 * Onboarding category chips show whole names (2026-09-26): the chip text had
 * maxWidth 100 with numberOfLines 1, so "Magic: The Gathering" read
 * "Magic: The G…". The grid wraps; the chip may be as wide as its name.
 * Static, like homeInitialLoading.test.ts: mounting onboarding needs the world.
 */
import { readFileSync } from 'fs';
import { join } from 'path';

const SRC = readFileSync(join(__dirname, '../../app/(auth)/onboarding.tsx'), 'utf8');

it('does not cap the chip text width', () => {
  const block = SRC.match(/categoryPillText:\s*\{([^}]*)\}/);
  expect(block).not.toBeNull();
  expect(block![1]).not.toMatch(/maxWidth\s*:\s*\d/);
});
