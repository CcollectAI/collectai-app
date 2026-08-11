#!/usr/bin/env node
/**
 * Fail when the server hands the app a category id the app cannot route to.
 *
 * `GET /search/unified` returns a `categories` array built from a hand-written
 * `CATEGORY_LIST` in `server/app/features/search_router.py`. Every `id` in it
 * is a ROUTE: `app/search.tsx` pushes `/categories/<id>`, and
 * `app/categories/[categoryId].tsx` resolves it with `getCategoryById` against
 * `src/data/categories.ts`. An id missing from that file renders the screen's
 * "Category not found" state.
 *
 * On 2026-08-11 three of the 36 ids were wrong: the server sent `pokemon_tcg`,
 * `sports_cards` and `kpop` where the app's ids are `pokemon`, `sportscards`
 * and `kpop_merch`. So searching "pokemon" — the likeliest query this app will
 * ever receive — produced a CATEGORIES row that dead-ended. Reported as
 * "search results are not pressable": the press fires, the screen changes, and
 * what arrives is an error state.
 *
 * This is its own AXIS. Nothing else could see it:
 *   - check-dead-nav          — asks whether the route FILE exists.
 *                               `app/categories/[categoryId].tsx` does. It has
 *                               no opinion on whether the id fills it.
 *   - check-route-param-handoff — asks whether the destination READS the param.
 *                               It does read `categoryId`; the value is what
 *                               is wrong.
 *   - tsc                     — the id is a string crossing an HTTP boundary.
 *                               There is no type to violate.
 * The route resolves, the param is read, the request 200s. Only comparing the
 * VALUES on the two sides finds it — the same shape as
 * `audit_key_overlap.py`, one seam further out.
 *
 * THE RULE: every id in a server list that the app turns into a route segment
 * must exist in the app's local taxonomy.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SERVER_FILE = 'server/app/features/search_router.py';
const TAXONOMY_FILE = 'src/data/categories.ts';

const py = readFileSync(resolve(ROOT, SERVER_FILE), 'utf8');
const ts = readFileSync(resolve(ROOT, TAXONOMY_FILE), 'utf8');

// Only the CATEGORY_LIST literal — not every `{"id": ...}` in the file, which
// would drag in unrelated dicts if any are ever added.
const listMatch = py.match(/^CATEGORY_LIST = \[([\s\S]*?)^\]/m);
if (!listMatch) {
  console.error(`check-search-category-ids: FAIL — could not find CATEGORY_LIST in ${SERVER_FILE}.`);
  console.error('  The gate cannot verify what it cannot parse. If the list moved, update this script.');
  process.exit(1);
}

const serverEntries = [...listMatch[1].matchAll(/\{\s*"id":\s*"([^"]+)",\s*"name":\s*"([^"]+)"\s*\}/g)]
  .map((m) => ({ id: m[1], name: m[2] }));

if (serverEntries.length === 0) {
  console.error(`check-search-category-ids: FAIL — CATEGORY_LIST parsed to 0 entries in ${SERVER_FILE}.`);
  console.error('  A gate that silently matches nothing is worse than no gate.');
  process.exit(1);
}

// `id: 'x',` at the top level of a Category object literal. Anchored to the
// 4-space indent the file uses for object members so `relatedCategoryIds`
// arrays and nested literals cannot contribute ids.
const feIds = new Set([...ts.matchAll(/^ {4}id: '([A-Za-z0-9_]+)',$/gm)].map((m) => m[1]));

if (feIds.size === 0) {
  console.error(`check-search-category-ids: FAIL — parsed 0 category ids from ${TAXONOMY_FILE}.`);
  process.exit(1);
}

const unroutable = serverEntries.filter((e) => !feIds.has(e.id));

if (unroutable.length === 0) {
  console.log(
    `check-search-category-ids: PASS — all ${serverEntries.length} search category ids resolve against ${feIds.size} app categories.`,
  );
  process.exit(0);
}

console.error(
  `check-search-category-ids: FAIL — ${unroutable.length} of ${serverEntries.length} search category ids have no screen to open.\n`,
);
for (const e of unroutable) {
  // Best-effort suggestion so the fix is obvious: the closest id that shares a
  // prefix. Advisory only — never applied automatically.
  const stem = e.id.split('_')[0];
  const near = [...feIds].filter((id) => id.startsWith(stem) || stem.startsWith(id.split('_')[0]));
  console.error(`  ${SERVER_FILE}  {"id": "${e.id}", "name": "${e.name}"}`);
  console.error(`      not in ${TAXONOMY_FILE}${near.length ? ` — did you mean: ${near.join(', ')}` : ''}`);
}
console.error(`
Fix: change the id in CATEGORY_LIST to the one the app actually routes with,
or add the category to ${TAXONOMY_FILE}. Do NOT map it in the screen —
app/search.tsx already drops unroutable rows so a drift cannot reach a user's
thumb, and a second mapping table would be a second place for these two lists
to disagree.
`);
process.exit(1);
