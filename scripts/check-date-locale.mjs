#!/usr/bin/env node
/**
 * A date a MEMBER reads must be formatted in the language they are reading.
 *
 * Two shapes both shipped, and neither is visible to anyone testing in English:
 *
 *   date.toLocaleDateString('en-US', …)   a Dutch member reads "Sep 16" on a
 *   date.toLocaleDateString('en-GB', …)   fully translated screen; the two
 *                                         charts disagreed with every other
 *                                         date on the same page
 *   date.toLocaleDateString()             DEVICE locale — right by accident on
 *                                         a matching device, wrong for anyone
 *                                         whose phone language differs from the
 *                                         app language they chose
 *
 * Twelve sites did the first two (class sweep H, 2026-09-17), including the
 * inbox, the chat thread, the week view, the sponsor dashboard and both charts.
 *
 * The answer is `dateLocale()` from `src/constants/dateFormats.ts`, which
 * SettingsProvider keeps pointed at the resolved UI language. It follows the
 * LANGUAGE, not `settings.numberLocale` — docs/ARCHITECTURE.md is explicit that
 * those are different sets.
 *
 * Exempt a genuine case with a reason on the line or just above:
 *     // locale-ok: server-rendered audit stamp, never shown to a member
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const SCAN = ['app', 'src'];
const SKIP_FILES = new Set([
  // defines dateLocale() itself
  'src/constants/dateFormats.ts',
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

// A literal locale string, or NO argument at all (device locale).
const HARDCODED = /\.toLocale(?:Date|Time)?String\(\s*['"][a-z]{2}(?:-[A-Z]{2})?['"]/;
const DEVICE = /\.toLocale(?:Date|Time)?String\(\s*\)/;

const findings = [];
for (const abs of SCAN.flatMap((d) => walk(join(ROOT, d)))) {
  const rel = relative(ROOT, abs);
  if (SKIP_FILES.has(rel)) continue;
  const lines = readFileSync(abs, 'utf8').split('\n');
  lines.forEach((line, i) => {
    const code = line.replace(/\/\/.*$/, '');
    const hard = HARDCODED.test(code);
    const device = DEVICE.test(code);
    if (!hard && !device) return;
    const near = lines.slice(Math.max(0, i - 3), i + 1).join('\n');
    if (/locale-ok:/.test(near)) return;
    findings.push({
      at: `${rel}:${i + 1}`,
      why: hard
        ? 'hard-coded locale — a member reading another language sees this date in English'
        : 'no locale argument — this is the DEVICE locale, not the app language',
      line: line.trim().slice(0, 100),
    });
  });
}

if (findings.length) {
  console.error(`✗ date locale — ${findings.length} date(s) not formatted in the member's language:`);
  for (const f of findings) {
    console.error(`   ${f.at}`);
    console.error(`      ${f.why}`);
    console.error(`      ${f.line}`);
  }
  console.error('\n   Use dateLocale() from src/constants/dateFormats.ts, or add');
  console.error('   "// locale-ok: <why this date is not read by a member>".');
  process.exit(1);
}
console.log('✓ date locale — every date follows the UI language, or says why it need not.');
