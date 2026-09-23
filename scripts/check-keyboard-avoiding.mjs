#!/usr/bin/env node
/**
 * Every <KeyboardAvoidingView> takes its `behavior` from
 * `KEYBOARD_AVOIDING_BEHAVIOR` (src/lib/keyboardAvoiding.ts).
 *
 * WHY: the app draws edge-to-edge on Android (Expo SDK 54, targetSdk 36), and
 * an edge-to-edge window is not resized for the soft keyboard. The pattern
 * copied across the app — `behavior={Platform.OS === 'ios' ? 'padding' :
 * undefined}` — therefore meant NO keyboard handling on Android. Walked
 * 2026-09-22: in a DM the message box sat under the keyboard, so a member could
 * not see what they typed. 20 screens carried the same ternary.
 *
 * Fails on a KeyboardAvoidingView whose opening tag has no `behavior`, or any
 * behavior other than `{KEYBOARD_AVOIDING_BEHAVIOR}`.
 *
 * Usage: node scripts/check-keyboard-avoiding.mjs   (npm run check:keyboard-avoiding)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const ROOTS = ['app', 'src'];

/**
 * Blank comments (keeping newlines, so line numbers stay right) so prose that
 * NAMES the component is never read as a use of it.
 *
 * A single-pass SCANNER, not two regexes. The first version stripped block
 * comments first, and a `//` line comment in app/(auth)/register.tsx contains
 * `/*)` inside a URL — so it opened a "block comment" that ran to the next
 * `* /` and blanked lines 154–258, hiding that screen's KeyboardAvoidingView.
 * The gate reported 25 sites where there are 26. Same trap as
 * check-unguarded-back.mjs: comment markers must be read in order, and not
 * inside strings.
 */
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
    else if (p.endsWith('.tsx')) files.push(p);
  }
};
for (const r of ROOTS) {
  try { walk(join(ROOT, r)); } catch { /* root may not exist */ }
}

const offenders = [];
let seen = 0;
for (const f of files) {
  const src = stripComments(readFileSync(f, 'utf8'));
  const re = /<KeyboardAvoidingView\b/g;
  let m;
  while ((m = re.exec(src))) {
    seen += 1;
    // The opening tag ends at the first `>` that is not part of `=>`.
    let i = m.index + m[0].length;
    let depth = 0;
    for (; i < src.length; i += 1) {
      const ch = src[i];
      if (ch === '{') depth += 1;
      else if (ch === '}') depth -= 1;
      else if (ch === '>' && depth === 0 && src[i - 1] !== '=') break;
    }
    const tag = src.slice(m.index, i + 1);
    const line = src.slice(0, m.index).split('\n').length;
    const behavior = tag.match(/\bbehavior=\{([^}]*)\}/);
    if (!behavior || behavior[1].trim() !== 'KEYBOARD_AVOIDING_BEHAVIOR') {
      offenders.push(`${relative(ROOT, f)}:${line}  behavior=${behavior ? `{${behavior[1].trim()}}` : '(none)'}`);
    }
  }
}

if (seen === 0) {
  // A gate that finds nothing to check may be blind, not clean.
  console.error('check:keyboard-avoiding found NO KeyboardAvoidingView at all — the scan is broken.');
  process.exit(1);
}
if (offenders.length) {
  console.error(`FAIL — ${offenders.length} of ${seen} KeyboardAvoidingView(s) do not use KEYBOARD_AVOIDING_BEHAVIOR:\n`);
  for (const o of offenders) console.error('  ' + o);
  console.error('\nUse: behavior={KEYBOARD_AVOIDING_BEHAVIOR}  (import from @/lib/keyboardAvoiding)');
  process.exit(1);
}
console.log(`PASS — all ${seen} KeyboardAvoidingView(s) use KEYBOARD_AVOIDING_BEHAVIOR`);
