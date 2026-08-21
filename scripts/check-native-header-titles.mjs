#!/usr/bin/env node
/**
 * check-native-header-titles — a native `headerTitle` must go through t().
 *
 * WHY THIS EXISTS
 *
 * `check-i18n-parity.mjs` compares KEYS across locale files, so it can only see
 * a string that already has a key. `check-i18n-strings.mjs` finds user-visible
 * strings in JSX that were never wrapped in `t()`. Neither can see this:
 *
 *     <Stack.Screen options={{ headerTitle: 'Scan Barcode' }} />
 *
 * It is not JSX text and it has no key to be missing, so both gates pass while
 * a Dutch or Japanese device shows an English bar title. Measured 2026-08-21:
 * 24 hardcoded native titles across 20 screens, against exactly ONE that used
 * `t()`. The failure is a missing KEY, not a missing translation — which is the
 * blind spot beside `learning_i18n_missing_key_renders_english`.
 *
 * `headerBackTitle` is covered too. It is rendered next to the chevron on every
 * pushed screen, so an English "Items" sits under a translated title.
 *
 * WHAT PASSES
 *   headerTitle: t('foo.bar')          // translated
 *   headerTitle: ''                    // deliberately no native title — the
 *                                      // documented iOS fix for a screen that
 *                                      // renders its own in-body heading
 *   headerTitle: someVariable          // computed; check-i18n-strings' problem
 *   headerTitle: cond ? t('a') : t('b')
 *
 * WHAT FAILS
 *   headerTitle: 'Scan Barcode'
 *   headerTitle: "Archived"
 *   headerBackTitle: "Items"
 *
 * Comments are stripped FIRST. A gate that counts a name inside a `//` comment
 * is the false positive `check-unrendered` had to be fixed for, and the same
 * one a hand-written `accessibilityRole="tabbar"` grep produced on 2026-08-22 —
 * both hits were comments warning against it.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOTS = ['app', 'src'];
const PROPS = ['headerTitle', 'headerBackTitle'];

/** Strip block and line comments, and string contents, so neither a comment nor
 *  a URL inside a literal can be mistaken for code. */
function stripComments(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    // line comments only to end-of-LINE — `//.*` with a dot-matches-newline
    // flag eats the rest of the file, which is exactly how a dead-style
    // checker written on 2026-08-22 reported 13 dead styles in a file with one.
    .replace(/\/\/[^\n]*/g, '');
}

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === 'node_modules' || name.startsWith('.')) continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (/\.(tsx|ts)$/.test(name)) out.push(p);
  }
  return out;
}

const offenders = [];
for (const root of ROOTS) {
  let files = [];
  try { files = walk(root); } catch { continue; }
  for (const file of files) {
    const src = stripComments(readFileSync(file, 'utf8'));
    const lines = src.split('\n');
    lines.forEach((line, i) => {
      for (const prop of PROPS) {
        // A STRING LITERAL immediately after the prop. Empty string is legal.
        const m = line.match(new RegExp(`\\b${prop}\\s*:\\s*(['"\`])((?:(?!\\1).)+)\\1`));
        if (m && m[2].trim()) {
          offenders.push({ file: relative(process.cwd(), file), line: i + 1, prop, value: m[2] });
        }
      }
    });
  }
}

if (offenders.length === 0) {
  console.log('[native-header-titles] PASS — every native header title goes through t().');
  process.exit(0);
}

console.error(`\n[native-header-titles] FAIL — ${offenders.length} hardcoded native header title(s).`);
console.error('A native bar title is invisible to both i18n gates: it is not JSX text,');
console.error('and it has no key for parity to find missing. On a non-English device');
console.error('these render in English under a translated screen.\n');
for (const o of offenders) {
  console.error(`  ${o.file}:${o.line}  ${o.prop}: ${JSON.stringify(o.value)}`);
}
console.error('\nFix: add a key to src/i18n/locales/*.json (all 7) and use t(...).');
console.error("     Or pass '' if the screen renders its own in-body heading.\n");
process.exit(1);
