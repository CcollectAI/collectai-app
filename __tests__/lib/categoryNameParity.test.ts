/**
 * One category, one name — in every list that names it (2026-09-26).
 *
 * A category's display name lives in four places: the constants list (pills,
 * pickers, onboarding), the taxonomy registry, the Explore page data and the
 * server's scan map. 22 slugs had drifted apart — "Pokémon" / "Pokémon TCG" /
 * "Pokémon Cards", "Artisan Keycaps" beside "Custom Keycaps" — and
 * check-category-parity compared slugs only, so it could not see it.
 * src/constants/categories.ts is canonical; every other list must match it.
 * (Same arrangement as test_currency_symbol_parity.py: two lists + a test.)
 */
import { readFileSync } from 'fs';
import { join } from 'path';

const root = join(__dirname, '../..');
const read = (p: string) => readFileSync(join(root, p), 'utf8');

const pairs = (src: string, re: RegExp) => {
  const out: Record<string, string> = {};
  for (const m of src.matchAll(re)) out[m[1]] = m[2].replace(/\\'/g, "'");
  return out;
};

const canonical = pairs(read('src/constants/categories.ts'), /\{\s*slug:\s*'([^']+)',\s*name:\s*'((?:[^'\\]|\\.)+)'/g);
const registry = pairs(read('src/taxonomy/registry.ts'), /\n {4}id:\s*'([^']+)',[^\n]*\n(?:\s*\/\/[^\n]*\n)*\s*name:\s*'((?:[^'\\]|\\.)+)'/g);
const explore = pairs(read('src/data/categories.ts'), /\n {2}\{\n {4}id:\s*'([^']+)',\n {4}name:\s*'((?:[^'\\]|\\.)+)'/g);
const server = pairs(read('server/app/features/quickscan_proxy_router.py'), /"([a-z0-9_]+)":\s*"([^"]+)"/g);

it('parsed every list (a broken pattern must not pass as "no mismatches")', () => {
  expect(Object.keys(canonical).length).toBeGreaterThan(50);
  expect(Object.keys(registry).length).toBeGreaterThan(40);
  expect(Object.keys(explore).length).toBeGreaterThan(50);
  expect(Object.keys(server).length).toBeGreaterThan(30);
});

it.each([
  ['taxonomy registry', registry],
  ['Explore page data', explore],
  ['server scan map', server],
])('%s names every category exactly as the constants list does', (_label, list) => {
  const drift = Object.entries(list)
    .filter(([slug, name]) => canonical[slug] && canonical[slug] !== name)
    .map(([slug, name]) => `${slug}: "${name}" should be "${canonical[slug]}"`);
  expect(drift).toEqual([]);
});
