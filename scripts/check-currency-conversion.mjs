#!/usr/bin/env node
/**
 * A EUR amount rendered with the member's currency symbol must be CONVERTED.
 *
 * `src/lib/format.ts` has two formatters and only one of them converts:
 *   fmtCurrency(amountEUR, settings)        → convertEUR() then format  ✅
 *   formatPrice(amount, currency, locale)   → formats AS GIVEN, no FX   ⚠️
 *
 * `formatPrice` is correct when the amount is ALREADY in that currency — a
 * marketplace listing carries its own `price` + `currency` columns, and
 * `items.purchase_currency` / `asking_currency` do the same. It is wrong when
 * the amount came out of the backend in EUR (`/portfolio/*`, `value_eur`,
 * `*_price_eur`, the catalogue): the number stays in euros while the symbol
 * changes, so a member whose region set USD (onboarding REGION_DEFAULTS) reads
 * "$1.348" for €1.347,68 — and a JPY member is off by ~160×.
 *
 * Found 2026-09-16 by a class sweep, after five device rounds missed it: the
 * walk account is EUR, where the two formatters agree.
 *
 * This gate flags `formatPrice(x, <member currency>)` — the currency argument
 * coming from settings/preferences rather than from the row being rendered.
 * Exempt a genuinely-already-converted site with a reason on the line above or
 * at the end of the line:
 *     // currency-ok: listing.price is stored in listing.currency
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const SCAN = ['app', 'src'];
const walk = (dir, out = []) => {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e === '__tests__' || e.startsWith('.')) continue;
    const f = join(dir, e);
    if (statSync(f).isDirectory()) walk(f, out);
    else if (/\.(ts|tsx)$/.test(e)) out.push(f);
  }
  return out;
};

// The currency argument names the MEMBER's preference rather than the row's own
// currency column. `settings.currency`, `currency` from useSettings(), etc.
const MEMBER_CURRENCY = /\b(settings|s|prefs|preferences)\s*\.\s*currency\b|\buserCurrency\b|\bdisplayCurrency\b/;
const findings = [];

for (const abs of SCAN.flatMap((d) => walk(join(ROOT, d)))) {
  const rel = relative(ROOT, abs);
  if (rel === 'src/lib/format.ts') continue; // the definitions themselves
  const src = readFileSync(abs, 'utf8');
  const lines = src.split('\n');
  for (const m of src.matchAll(/\bformatPrice\s*\(/g)) {
    // balanced-paren read of the argument list
    let depth = 0, i = m.index + m[0].length - 1, end = -1;
    for (; i < src.length; i++) {
      if (src[i] === '(') depth++;
      else if (src[i] === ')') { if (--depth === 0) { end = i; break; } }
    }
    if (end < 0) continue;
    const args = src.slice(m.index + m[0].length, end);
    // split top-level commas only
    const parts = []; let d2 = 0, cur = '';
    for (const ch of args) {
      if ('([{'.includes(ch)) d2++;
      if (')]}'.includes(ch)) d2--;
      if (ch === ',' && d2 === 0) { parts.push(cur); cur = ''; continue; }
      cur += ch;
    }
    parts.push(cur);
    const currencyArg = (parts[1] ?? '').trim();
    if (!currencyArg || !MEMBER_CURRENCY.test(currencyArg)) continue;
    const ln = src.slice(0, m.index).split('\n').length;
    const here = lines[ln - 1] ?? '';
    const above = lines[ln - 2] ?? '';
    if (/currency-ok:/.test(here) || /currency-ok:/.test(above)) continue;
    findings.push(`${rel}:${ln}  formatPrice(…, ${currencyArg.slice(0, 40)}) — member currency on an unconverted amount`);
  }
}

// Second shape, same defect, invisible to the formatPrice check above: a
// currency SYMBOL typed into a template literal — `€${value}`. It prints euros
// whatever the member chose, and never converts (found 2026-09-24 on profile
// cards, the stats tile and derived alert text). Comments are blanked first so
// prose quoting the pattern is not a finding.
const HAND_BUILT = /(?:€|\\u20AC|£|¥)\$\{/;
for (const abs of SCAN.flatMap((d) => walk(join(ROOT, d)))) {
  const rel = relative(ROOT, abs);
  if (rel === 'src/lib/format.ts') continue;
  const src = readFileSync(abs, 'utf8');
  if (!HAND_BUILT.test(src)) continue;
  const lines = src.split('\n');
  const code = src
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
    .split('\n')
    .map((l) => l.replace(/(^|[^:'"`])\/\/.*$/, '$1'));
  code.forEach((line, i) => {
    if (!HAND_BUILT.test(line)) return;
    if (/currency-ok:/.test(lines[i]) || /currency-ok:/.test(lines[i - 1] ?? '')) return;
    findings.push(`${rel}:${i + 1}  hand-built currency string — ${lines[i].trim().slice(0, 70)}`);
  });
}

if (findings.length) {
  console.error(`✗ currency conversion — ${findings.length} site(s) label an amount with the member's currency without converting it:`);
  for (const f of findings) console.error(`   ${f}`);
  console.error('\n   Use fmtCurrency(amountEUR, settings) for backend EUR amounts, or add');
  console.error('   "// currency-ok: <why this amount is already in that currency>".');
  process.exit(1);
}
console.log('✓ currency conversion — every member-currency render converts, or says why it need not.');
