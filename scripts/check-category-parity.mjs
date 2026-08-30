#!/usr/bin/env node
/**
 * The app defines its categories TWICE and nothing kept them in step.
 *
 *   src/constants/categories.ts  — {slug, name, tint}. Read by the ADD and SELL
 *                                  flows: add-manual, quickscan, sell/pick,
 *                                  sell/new, search, items, wishlist.
 *   src/data/categories.ts       — union type + {accentColor, iconName}. Read by
 *                                  categories/index, onboarding, guides,
 *                                  leaderboard, franchise, events.
 *
 * On 2026-08-30 `jewellery` was in the second and not the first. It had 435
 * catalogue rows, 5,425 eBay price rows, a taxonomy mapper entry and a
 * marketplaceApi rule routing it to authenticated sale above EUR 1000 — and no
 * user could put anything in it, because the picker reads the list it was
 * missing from. Browsable, unfillable: a whole category reachable from nowhere.
 *
 * Nothing caught it. `tsc` is happy — the two files share no type. The union in
 * data/categories.ts is the wider list, so a slug missing from constants is not
 * a type error in either direction.
 *
 * THE RULE: the two slug sets must be identical. Not "constants is a subset" —
 * a slug in constants but not in data would render with no icon or accent.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join } from 'node:path';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const constantsSrc = readFileSync(join(ROOT, 'src/constants/categories.ts'), 'utf8');
const dataSrc = readFileSync(join(ROOT, 'src/data/categories.ts'), 'utf8');

const A = new Set([...constantsSrc.matchAll(/slug: '([a-z_0-9]+)'/g)].map((m) => m[1]));
const B = new Set([
  ...[...dataSrc.matchAll(/^\s*\|\s*'([a-z_0-9]+)'/gm)].map((m) => m[1]),
  ...[...dataSrc.matchAll(/^\s{2}([a-z_0-9]+): \{ accentColor/gm)].map((m) => m[1]),
]);

// An empty parse is indistinguishable from agreement; refuse to pass on it.
if (A.size === 0 || B.size === 0) {
  console.error(`[category-parity] FAIL — parsed ${A.size} / ${B.size} slugs. An empty\n` +
    '  parse would make any two files "agree", which is the failure this gate exists\n' +
    '  to catch. The file format changed; fix the patterns above.');
  process.exit(1);
}

const onlyData = [...B].filter((s) => !A.has(s)).sort();
const onlyConstants = [...A].filter((s) => !B.has(s)).sort();

if (onlyData.length || onlyConstants.length) {
  console.error('[category-parity] FAIL\n');
  if (onlyData.length) {
    console.error(`  - In src/data/categories.ts but NOT src/constants/categories.ts: ${onlyData.join(', ')}\n` +
      '      These are browsable and UNFILLABLE — the add/sell pickers read constants,\n' +
      '      so a user can open the category and never put anything in it.\n');
  }
  if (onlyConstants.length) {
    console.error(`  - In src/constants/categories.ts but NOT src/data/categories.ts: ${onlyConstants.join(', ')}\n` +
      '      These render with no accent colour and no icon.\n');
  }
  process.exit(1);
}
console.log(`[category-parity] PASS — both lists define the same ${A.size} categories.`);
