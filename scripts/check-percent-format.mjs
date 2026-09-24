#!/usr/bin/env node
/**
 * No hand-built percentages: every "%" figure goes through `formatPercent`
 * (src/lib/format.ts).
 *
 * WHY: `.toFixed(1)}%` always prints a DOT, while money follows the member's
 * number locale. Walked on Android 2026-09-23 with a comma-decimal locale:
 * "€60,00" beside "+18.9%" on one Analytics screen. ~20 sites carried the
 * pattern, so the fix is one formatter plus this gate, not a sweep.
 *
 * Flags `toFixed(<n>)` whose result is followed by a `%` on the same line
 * (template `}%`, JSX `}%`, or `+ '%'`). Comments are stripped by a real
 * scanner so prose that quotes the pattern is not a finding.
 *
 * Exempt a line that is genuinely not member-facing (a log, a style width)
 * with `// percent-format-ok: <reason>` on the line above.
 *
 * Usage: node scripts/check-percent-format.mjs   (npm run check:percent-format)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const ROOTS = ['app', 'src'];

function stripComments(s) {
  let out = '';
  let i = 0;
  let quote = null;
  while (i < s.length) {
    const ch = s[i];
    const nx = s[i + 1];
    if (quote) {
      out += ch;
      if (ch === '\\') { out += nx ?? ''; i += 2; continue; }
      if (ch === quote) quote = null;
      i += 1;
      continue;
    }
    if (ch === '/' && nx === '/') {
      while (i < s.length && s[i] !== '\n') { out += ' '; i += 1; }
      continue;
    }
    if (ch === '/' && nx === '*') {
      const end = s.indexOf('*/', i + 2);
      const stop = end === -1 ? s.length : end + 2;
      out += s.slice(i, stop).replace(/[^\n]/g, ' ');
      i = stop;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === '`') quote = ch;
    out += ch;
    i += 1;
  }
  return out;
}

const files = [];
const walk = (dir) => {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e === '__tests__' || e.startsWith('.')) continue;
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.(ts|tsx)$/.test(p)) files.push(p);
  }
};
for (const r of ROOTS) {
  try { walk(join(ROOT, r)); } catch { /* root may not exist */ }
}

// `String(Math.round(x * 100) / 100)` seeds a money input with a DOT decimal
// (Sell price, item value — 2026-09-24). moneyInputValue() follows the locale.
const MONEY_SEED = /String\(\s*Math\.round\((?:[^()]|\([^()]*\))*\*\s*100\s*\)\s*\/\s*100\s*\)/;
const DECIMAL_PLACEHOLDER = /placeholder=(\{\s*`[^`]*|\{?\s*['"])0[.,]0+\b/;
const PATTERN = /toFixed\(\s*\d\s*\)\s*(\}\s*%|\+\s*['"`]\s*%)/;
const offenders = [];
let scanned = 0;
for (const f of files) {
  const raw = readFileSync(f, 'utf8');
  if (!raw.includes('toFixed') && !raw.includes('placeholder') && !raw.includes('Math.round')) continue;
  scanned += 1;
  const rawLines = raw.split('\n');
  const code = stripComments(raw).split('\n');
  code.forEach((line, i) => {
    // Same defect in an input: a literal "0.00" placeholder tells a
    // comma-decimal member to type a dot (Create Event, 2026-09-24).
    if (MONEY_SEED.test(line)) {
      offenders.push(`${relative(ROOT, f)}:${i + 1}  ${rawLines[i].trim().slice(0, 110)}  → moneyInputValue()`);
      return;
    }
    if (DECIMAL_PLACEHOLDER.test(line)) {
      offenders.push(`${relative(ROOT, f)}:${i + 1}  ${rawLines[i].trim().slice(0, 110)}  → moneyInputPlaceholder()`);
      return;
    }
    if (!PATTERN.test(line)) return;
    if (/percent-format-ok:\s*\S/.test(rawLines[i - 1] ?? '')) return;
    offenders.push(`${relative(ROOT, f)}:${i + 1}  ${rawLines[i].trim().slice(0, 110)}`);
  });
}

if (scanned === 0) {
  console.error('check:percent-format scanned no file containing toFixed or a placeholder — the scan is broken.');
  process.exit(1);
}
if (offenders.length) {
  console.error(`FAIL — ${offenders.length} hand-built percentage(s) / decimal placeholder(s); use formatPercent() / moneyInputPlaceholder() from @/lib/format:\n`);
  for (const o of offenders) console.error('  ' + o);
  process.exit(1);
}
console.log(`PASS — no hand-built percentages (${scanned} files with toFixed or a placeholder scanned)`);
