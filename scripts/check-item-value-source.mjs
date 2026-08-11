#!/usr/bin/env node
/**
 * Fail when the app goes back to deciding for itself what an item is worth.
 *
 * Measured on prod 2026-08-11: the client derived an item's value as
 * `quick_predictions -> predicted_price_eur -> estimated_value`, while every
 * server surface used `quick_predictions -> price_predictions ->
 * predicted_price_eur -> estimated_value`. The missing middle link meant 15 of
 * 34 active items (44%) rendered EUR 0 in the app while the server held a
 * value. Per category: one_piece_tcg's Portfolio tile said EUR 80.64 where the
 * list summed to EUR 0.00; pokemon EUR 55.57 against EUR 15.00.
 *
 * Nothing errored, and nothing could: an item priced at 0 is a valid item, so
 * the two numbers were simply different on two screens that never appeared
 * together. Making the tile pressable is what puts them one tap apart.
 *
 * The fix made `public.v_item_values_v1` the single definition and had the
 * client CONSUME it rather than re-derive it. This gate protects the two ways
 * that can quietly come undone:
 *
 *   1. The view disappears from the schema lock (dropped or renamed) — the
 *      client's read then returns nothing and every item falls back to the old,
 *      wrong chain. Silently, because the fallback is deliberate.
 *   2. A NEW read path is added that calls `mapItemRow` directly instead of
 *      going through `mapRowsWithValues`. There were already three read paths
 *      (listItems, searchItems, listArchivedItems) all ending in the same
 *      `.map(mapItemRow)`; a fourth is the obvious next step and would get the
 *      old chain with no error and no failing test.
 *
 * This is its own AXIS. No existing gate covers it: check-silent-failures asks
 * whether an error is swallowed (nothing errors here), check-constraint-drift
 * asks whether a written value is legal, and tsc cannot see that two numeric
 * expressions in two languages are supposed to agree.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const PROVIDER = 'src/data/providers/itemsProvider.ts';
const LOCK = 'scripts/schema.lock.json';
const VIEW = 'v_item_values_v1';

const failures = [];

// 1. The view must still exist in the committed schema lock.
const lock = JSON.parse(readFileSync(resolve(ROOT, LOCK), 'utf8'));
if (!Object.prototype.hasOwnProperty.call(lock.tables ?? {}, VIEW)) {
  failures.push(
    `${LOCK}: \`${VIEW}\` is missing.\n` +
    `      The client reads this view for every item's value. Without it the read\n` +
    `      returns nothing and every item silently falls back to the stale chain.`,
  );
}

const src = readFileSync(resolve(ROOT, PROVIDER), 'utf8');

// 2. The provider must actually read the view.
if (!src.includes(`.from('${VIEW}')`)) {
  failures.push(
    `${PROVIDER}: no read of \`${VIEW}\`.\n` +
    `      Item values must come from the view, not be recomputed on the client.`,
  );
}

// 3. `mapItemRow` may be CALLED from exactly one place: mapRowsWithValues.
// Comments and the definition itself don't count, so strip both first.
const stripped = src
  .replace(/\/\*[\s\S]*?\*\//g, '')     // block comments
  .replace(/^\s*\/\/.*$/gm, '');         // line comments
const lines = stripped.split('\n');
const callSites = [];
lines.forEach((line, i) => {
  // A call, not the declaration.
  if (/\bmapItemRow\s*\(/.test(line) && !/function\s+mapItemRow/.test(line)) {
    callSites.push({ line: i + 1, text: line.trim() });
  }
});

if (callSites.length !== 1) {
  failures.push(
    `${PROVIDER}: \`mapItemRow\` is called from ${callSites.length} place(s); exactly 1 is allowed.\n` +
    callSites.map((c) => `        line ${c.line}: ${c.text.slice(0, 90)}`).join('\n') +
    `\n      Every read path must go through \`mapRowsWithValues\`, which attaches the\n` +
    `      canonical value. A direct call gets the fallback chain and renders EUR 0\n` +
    `      for catalog-priced items — the exact 44% regression this gate exists for.`,
  );
}

if (failures.length === 0) {
  console.log(
    `check-item-value-source: PASS — ${VIEW} is locked, the provider reads it, and mapItemRow has a single call site.`,
  );
  process.exit(0);
}

console.error(`check-item-value-source: FAIL — ${failures.length} problem(s).\n`);
for (const f of failures) console.error(`  ${f}\n`);
console.error(
  `The canonical value lives in ONE place: public.${VIEW}.\n` +
  `Consume it; do not re-derive it. See docs/ARCHITECTURE.md value-sources.\n`,
);
process.exit(1);
