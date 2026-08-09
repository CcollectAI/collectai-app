#!/usr/bin/env node
/**
 * Fail on locale-unsafe parsing of a user-typed number.
 *
 * THE BUG THIS EXISTS FOR
 *
 * `app/watchlist-builder.tsx` parsed a target price with:
 *
 *     parseFloat(newTargetPrice.replace(/[^\d.]/g, "").trim())
 *
 * The character class keeps digits and a DOT and silently drops the COMMA. The
 * app ships in 7 currencies and most of Europe types `12,50`, which becomes
 * `1250` — a **hundredfold** target price. It does not throw, does not warn, and
 * produces a number that looks entirely plausible in the UI. The watchlist row
 * saves fine and simply never fires, because nothing is ever listed at 100× the
 * price the user meant.
 *
 * That is the whole class: **user types money, code silently produces a
 * different number.** Unlike a crash or an empty list, the output is a valid
 * number — so no test, no type check and no runtime guard notices.
 *
 * THE FOUR SHAPES, all of which produce a wrong number rather than an error
 *
 *   1. `replace(/[^\d.]/g, '')`      "12,50" -> "1250"     100x too big
 *   2. `replace(/[^\d,]/g, '')`      "12.50" -> "1250"     100x too big
 *   3. `parseFloat(x)` on raw input  "12,50" -> 12         silently truncated
 *   4. keeps BOTH `.` and `,` but                          parseFloat stops at
 *      never normalises                "1,5" -> 1           the first comma
 *
 * THE SAFE FORM — strip everything except digits and BOTH separators, then
 * normalise the comma to a dot before parsing:
 *
 *     parseFloat(value.replace(/[^0-9.,]/g, '').replace(',', '.'))
 *
 * WHY A CHECKER AND NOT A LINT RULE
 *
 * There is no ESLint rule for "this regex loses a decimal separator" — it is
 * specific to how this app takes money from users across 7 currencies. And the
 * bug was found by editing that exact line for an unrelated reason, which is
 * not a strategy. Everything in this repo that can only be found by luck should
 * become a check (scripts/audit_all.mjs).
 *
 * SCOPE — deliberately narrow, to stay a hard gate rather than a review queue.
 * Only flags a numeric parse whose input passes through a character class that
 * loses a separator, or a bare parse of an identifier that is obviously money.
 * Everything else (parsing an id, an index, a count) is untouched.
 *
 * Usage: node scripts/check-locale-number-parsing.mjs   (npm run check:numbers)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOTS = ['app', 'src'];
const EXTS = ['.ts', '.tsx'];

// Each entry needs a reason that is TRUE and re-checkable. An allowlist with a
// wrong justification is worse than no allowlist — it answers the reviewer's
// question and ends the investigation (see audit_rls_coverage.py, where
// `user_notifications` was excused as "served through /notifications" and sat
// unread for seven months).
const ALLOWLIST = new Map([
  ['scripts/check-locale-number-parsing.mjs',
   'This file documents the bad patterns in its own comments.'],
  ['src/lib/format.ts',
   'parseMoney IS the canonical safe parser — it necessarily contains the character class.'],
  ['src/lib/marketProviders/adapters/ebay-adapter.ts',
   'item.price.value comes from the eBay API, which is always dot-decimal per its schema. Not user input, so there is no comma to lose.'],
]);

/** Identifiers that hold money a user typed. A parse of one of these without
 *  separator handling is the bug, whatever the surrounding shape. */
// `total` is deliberately NOT bare: totalVols, totalCount and totalItems are
// counts, and flagging them would train the reader to ignore this check. Only
// totalPrice/totalCost/totalValue qualify.
const MONEY_RE =
  /\b(price|amount|cost|budget|shipping|fee|paid|payout|subtotal|targetPrice|askingPrice|offerAmount|total(Price|Cost|Value|Amount))[A-Za-z]*\b/i;

/**
 * Strip comments and string literals so a pattern quoted in a docstring is not
 * a finding. `check-unguarded-back.mjs` records why this matters: an
 * `indexOf('//')` version truncated at the `//` inside a URL and scanned the
 * rest of the line as CLEAN — a gate with a false negative is worse than none.
 */
function strip(src) {
  let out = '';
  let i = 0;
  const n = src.length;
  let state = 'code'; // code | line | block | sq | dq | tpl | regex
  while (i < n) {
    const c = src[i];
    const nx = src[i + 1];
    if (state === 'code') {
      if (c === '/' && nx === '/') { state = 'line'; i += 2; continue; }
      if (c === '/' && nx === '*') { state = 'block'; i += 2; continue; }
      if (c === "'") { state = 'sq'; i++; out += ' '; continue; }
      if (c === '"') { state = 'dq'; i++; out += ' '; continue; }
      if (c === '`') { state = 'tpl'; i++; out += ' '; continue; }
      // A regex literal must SURVIVE — the character class is the evidence.
      out += c; i++; continue;
    }
    if (state === 'line') { if (c === '\n') { state = 'code'; out += '\n'; } i++; continue; }
    if (state === 'block') { if (c === '*' && nx === '/') { state = 'code'; i += 2; } else { if (c === '\n') out += '\n'; i++; } continue; }
    if (state === 'sq' || state === 'dq' || state === 'tpl') {
      const q = state === 'sq' ? "'" : state === 'dq' ? '"' : '`';
      if (c === '\\') { i += 2; continue; }
      if (c === q) { state = 'code'; }
      if (c === '\n') out += '\n';
      i++; continue;
    }
  }
  return out;
}

function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e === '__tests__' || e.startsWith('.')) continue;
    const p = join(dir, e);
    const st = statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (EXTS.some((x) => p.endsWith(x))) out.push(p);
  }
  return out;
}

const findings = [];

for (const root of ROOTS) {
  let files = [];
  try { files = walk(root); } catch { continue; }
  for (const file of files) {
    const rel = relative(process.cwd(), file);
    if (ALLOWLIST.has(rel)) continue;  // reason recorded above
    const raw = readFileSync(file, 'utf8');
    const code = strip(raw);
    const lines = code.split('\n');
    // The RAW line is needed to see a normalisation like `.replace(',', '.')`:
    // strip() blanks string literals, so on the stripped line it reads
    // `.replace( , )` and the fix becomes invisible. Checking the stripped line
    // for the BUG and the raw line for the FIX is the only combination that is
    // correct for both — this checker flagged its own fixed code before that.
    const rawLines = raw.split('\n');

    lines.forEach((line, idx) => {
      const at = `${rel}:${idx + 1}`;
      const rawLine = rawLines[idx] ?? '';

      // --- 1 & 2: a character class that keeps ONE separator ---------------
      // Matches /[^\d.]/ , /[^0-9.]/ , /[^\d,]/ , /[^0-9,]/ and friends.
      const cls = line.match(/\[\^([^\]]*)\]/g) || [];
      for (const c of cls) {
        const keepsDigits = /\\d|0-9/.test(c);
        if (!keepsDigits) continue;
        const dot = c.includes('.');
        const comma = c.includes(',');
        if (dot !== comma) {
          findings.push({
            at,
            why: `character class ${c} keeps ${dot ? 'a dot but drops the comma' : 'a comma but drops the dot'} — "12${dot ? ',' : '.'}50" becomes 1250`,
            line: line.trim().slice(0, 110),
          });
          return;
        }
        // --- 4: keeps both but never normalises --------------------------
        const normalises = /replace\s*\(\s*(['"]),\1\s*,\s*(['"])\.\2\s*\)/.test(rawLine)
          || /replace\s*\(\s*\/,\/g?\s*,\s*(['"])\.\1\s*\)/.test(rawLine);
        if (dot && comma && !normalises) {
          findings.push({
            at,
            why: `character class ${c} keeps BOTH separators but the line does not normalise "," to "." — parseFloat stops at the comma, so "1,5" parses as 1`,
            line: line.trim().slice(0, 110),
          });
          return;
        }
      }

      // --- 3: a bare parse of an obviously-money identifier ----------------
      const bare = line.match(/\b(parseFloat|parseInt|Number)\s*\(\s*([A-Za-z_$][\w$.]*)\s*[),]/);
      if (bare) {
        const arg = bare[2];
        if (!MONEY_RE.test(arg)) return;
        // Already normalised somewhere on the line, or reading a NUMBER back
        // out of a typed object rather than off an input.
        if (/replace|toFixed|Number\(\s*\w+\.\w+\s*\)/.test(line)) return;
        findings.push({
          at,
          why: `${bare[1]}(${arg}) parses a money value straight — a typed "12,50" truncates to 12`,
          line: line.trim().slice(0, 110),
        });
      }
    });
  }
}

if (findings.length === 0) {
  console.log('check:numbers — no locale-unsafe number parsing');
  process.exit(0);
}

console.log(`check:numbers — ${findings.length} locale-unsafe parse${findings.length === 1 ? '' : 's'}\n`);
for (const f of findings) {
  console.log(`  ${f.at}`);
  console.log(`      ${f.why}`);
  console.log(`      ${f.line}\n`);
}
console.log("  Safe form: value.replace(/[^0-9.,]/g, '').replace(',', '.') then parseFloat");
process.exit(1);
