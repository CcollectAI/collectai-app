#!/usr/bin/env node
/**
 * A partial count must be marked partial, and the marking must come from the
 * PAGINATION — not from a literal.
 *
 * `partialCount(loaded, hasMore)` and `listingsCountLabel(loaded, hasMore)`
 * append the `+` that stops the first page reading as the total. Both take the
 * flag as an argument, so both can be defeated by passing `false`:
 *
 *     partialCount(filteredPast.length, false)      // silently back to the bug
 *
 * That is not hypothetical. When the helpers landed (2026-09-18) the three call
 * sites were mutated to `false` and **nothing caught it** — 137 suites green,
 * `tsc` 0. The helpers' own tests pin the helpers, not the wiring, and no test
 * renders a 1,300-line screen. So the fix was one edit away from being undone
 * by an autocomplete, with a green tree either way.
 *
 * This checks the one thing that is decidable: the flag argument is not a
 * boolean literal.
 *
 * A deliberate literal is allowed with a reason within three lines above:
 *
 *     {/* partial-ok: inside !hasMore, this sentence claims completeness *\/}
 *     That's all {listingsCountLabel(listings.length, false)}.
 *
 * Both comment forms are accepted, because the sites are in JSX: `//` is not a
 * comment in JSX children position — it renders as text — so a marker that only
 * worked as `//` would be unwritable exactly where it is needed
 * (`learning_four_ways_a_new_gate_is_wrong`, failure mode 2).
 *
 * What this does NOT catch, stated so nobody trusts it further than it goes: a
 * NEW screen that renders `list.length` and never adopts either helper. That
 * shape was swept by hand across the six `usePaginatedList` screens on
 * 2026-09-18 (events.tsx had four inline copies and two were wrong); making it
 * decidable means telling a count apart from a `=== 0` guard, and the version
 * that tried produced more noise than findings.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const SCAN = ['app', 'src'];
const SKIP_FILES = new Set([
  // define the helpers themselves; their docstrings name the signature
  'src/lib/partialCount.ts',
  'src/lib/listingsCountLabel.ts',
]);

const walk = (dir, out = []) => {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e === '__tests__' || e.startsWith('.')) continue;
    const f = join(dir, e);
    if (statSync(f).isDirectory()) walk(f, out);
    else if (/\.(ts|tsx)$/.test(e)) out.push(f);
  }
  return out;
};

// The flag is the SECOND argument. `[^,()]*` keeps this to a single simple
// first argument (`x.length`, `items.length`) rather than trying to balance
// parens with a regex — a nested call in the first argument is reported as
// unmatched rather than silently skipped.
const LITERAL_FLAG = /\b(partialCount|listingsCountLabel)\(\s*[^,()]*,\s*(true|false)\s*\)/;
const ANY_CALL = /\b(partialCount|listingsCountLabel)\(/;

const findings = [];
for (const abs of SCAN.flatMap((d) => walk(join(ROOT, d)))) {
  const rel = relative(ROOT, abs);
  if (SKIP_FILES.has(rel)) continue;
  const lines = readFileSync(abs, 'utf8').split('\n');
  lines.forEach((line, i) => {
    if (!ANY_CALL.test(line)) return;
    const m = LITERAL_FLAG.exec(line);
    if (!m) return;
    const near = lines.slice(Math.max(0, i - 3), i + 1).join('\n');
    if (/partial-ok:/.test(near)) return;
    findings.push({
      at: `${rel}:${i + 1}`,
      fn: m[1],
      lit: m[2],
      line: line.trim().slice(0, 110),
    });
  });
}

if (findings.length) {
  console.error(`✗ partial count — ${findings.length} count(s) marked from a literal, not from the pagination:`);
  for (const f of findings) {
    console.error(`   ${f.at}`);
    console.error(`      ${f.fn}(…, ${f.lit}) — a loaded count can only say "+" if it is told there is more`);
    console.error(`      ${f.line}`);
  }
  console.error('\n   Pass the hook\'s `hasMore`, or add a reason within three lines above:');
  console.error('   {/* partial-ok: <why this count really is complete here> */}');
  process.exit(1);
}
console.log('✓ partial count — every partial count is marked from its pagination, or says why not.');
