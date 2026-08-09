#!/usr/bin/env node
/**
 * Fail on a bare `router.back()`.
 *
 * `router.back()` is a SILENT no-op when the stack has nothing to pop — the
 * haptic fires, the button animates, nothing happens, and the user is stranded
 * on a pushed screen. It reproduced on three different screens before anyone
 * traced it to the shared pattern rather than to each screen.
 *
 * A screen can legitimately have an empty stack: a push-notification tap, any
 * `sparrow://` deep link, a cold start restored onto a non-tab route, or a
 * `router.replace` (QuickNavBar uses replace for all five tabs). None of that
 * is visible from the call site, which is why the rule is "always guard"
 * rather than "guard where it matters".
 *
 * Use `safeGoBack(router)` from `@/lib/goBack` instead.
 *
 * Usage: node scripts/check-unguarded-back.mjs   (npm run check:back)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOTS = ['app', 'src'];
const EXTS = ['.ts', '.tsx'];

// goBack.ts is the guarded implementation itself. ScreenHeader guards inline
// because it is the shared header and predates the helper.
const ALLOWLIST = new Set([
  'src/lib/goBack.ts',
  'src/components/ScreenHeader.tsx',
]);

const offenders = [];

/**
 * Blank out comments and string literals, leaving code positions intact.
 *
 * Must be a real scanner, not `indexOf('//')`. A naive comment strip truncates
 * at the `//` inside a URL, so
 *
 *     const help = 'https://example.com'; router.back();
 *
 * reads as "everything after the quote is a comment" and the violation is
 * SILENTLY MISSED — the exact failure mode this checker exists to prevent,
 * reproduced inside the checker itself. Verified: before this, that line
 * scanned clean.
 *
 * Comments are stripped so the checker doesn't flag prose explaining the rule;
 * strings are stripped so a `router.back()` inside a string literal (docs, test
 * fixtures) isn't a false positive. `state` carries block-comment nesting
 * across lines.
 */
function stripNonCode(line, state) {
  let out = '';
  let quote = null; // "'" | '"' | '`'

  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    const next = line[i + 1];

    if (state.inBlockComment) {
      if (ch === '*' && next === '/') {
        state.inBlockComment = false;
        i += 1;
      }
      continue;
    }

    if (quote) {
      if (ch === '\\') { i += 1; continue; }   // escaped char, skip both
      if (ch === quote) quote = null;
      continue;
    }

    if (ch === "'" || ch === '"' || ch === '`') { quote = ch; continue; }
    if (ch === '/' && next === '/') break;                    // line comment
    if (ch === '/' && next === '*') { state.inBlockComment = true; i += 1; continue; }

    out += ch;
  }

  return out;
}

function walk(dir) {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry.startsWith('.')) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      walk(full);
      continue;
    }
    if (!EXTS.some((e) => full.endsWith(e))) continue;

    const rel = relative(process.cwd(), full);
    if (ALLOWLIST.has(rel)) continue;

    const src = readFileSync(full, 'utf8');
    const state = { inBlockComment: false };

    src.split('\n').forEach((line, i) => {
      const code = stripNonCode(line, state);

      if (/\brouter\.back\(\)/.test(code)) {
        offenders.push({ file: rel, line: i + 1, text: line.trim() });
      }
    });
  }
}

for (const root of ROOTS) {
  try {
    walk(root);
  } catch {
    // root absent — nothing to check
  }
}

if (offenders.length === 0) {
  console.log('check:back — no unguarded router.back() calls');
  process.exit(0);
}

console.error(`check:back — ${offenders.length} unguarded router.back() call(s):\n`);
for (const o of offenders) {
  console.error(`  ${o.file}:${o.line}`);
  console.error(`    ${o.text}`);
}
console.error('\nUse safeGoBack(router) from "@/lib/goBack" — router.back() is a');
console.error('silent no-op when the navigation stack is empty.');
process.exit(1);
