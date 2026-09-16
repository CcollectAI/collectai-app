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
 *   5. keeps both and SWAPS the comma  "1.250,00" -> 1.25   the thousands dot
 *      for a dot                                            is read as decimal
 *
 * Shape 5 is the one this file itself used to recommend, and it is why the class
 * kept coming back: `.replace(',', '.')` reads as a fix, passes review, and is
 * only wrong once a member types a thousands separator — i.e. exactly on the
 * biggest amounts. A `/,/g` variant is no better. `useItemDetail.onSubmitSalePrice`
 * recorded a €1.250,00 sale as 1.25 through this shape, with this gate green
 * (2026-09-16).
 *
 * THE SAFE FORM — there is one, and it is not an idiom you retype:
 *
 *     parseMoney(value)   // src/lib/format.ts — LAST separator is the decimal
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
const MONEY_WORDS = new Set([
  'price', 'prices', 'amount', 'cost', 'budget', 'shipping', 'fee', 'fees', 'paid',
  'payout', 'subtotal', 'value', 'money', 'salary', 'balance', 'proceeds', 'net',
]);
// Words that make an identifier a COUNT or an ID, whatever else it contains:
// totalCount, itemsCount, priceId, valueIndex.
const NOT_MONEY_WORDS = new Set(['count', 'qty', 'quantity', 'index', 'id', 'ids', 'len', 'length', 'pct', 'percent', 'source', 'type', 'label', 'key']);

/** Split an identifier into words: camelCase, snake_case, dotted paths. */
function identifierWords(name) {
  return name
    .replace(/[_.\-]/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
}

/** Does this identifier hold money a MEMBER typed?
 *  `\b(price|…)` missed every camelCase name — maxPriceField, salePrice,
 *  ticketPriceCents and editableValue all read as "not money", which is why the
 *  four worst sites of the 2026-09-16 class sweep were invisible to this gate. */
function isMoneyIdentifier(name) {
  const words = identifierWords(name);
  if (words.some((w) => NOT_MONEY_WORDS.has(w))) return false;
  // A BARE `value` is the generic name of every validator, filter callback and
  // numeric param in the codebase — flagging it trains the reader to ignore
  // this gate. A compound (`editableValue`, `salePrice`, `maxPriceField`) is
  // the money shape.
  if (words.length === 1 && (words[0] === 'value' || words[0] === 'net')) return false;
  return words.some((w) => MONEY_WORDS.has(w));
}

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
        // --- 4 & 5: keeps both separators ---------------------------------
        // The ONLY safe consumer is parseMoney. A comma→dot swap used to be
        // accepted here and is shape 5: it is wrong the moment a thousands
        // separator is present, which is why this rule was green while a
        // €1.250,00 sale was recorded as 1.25.
        if (dot && comma) {
          if (/\bparseMoney\s*\(/.test(rawLine)) return;
          const swaps = /replace\s*\(\s*(['"]),\1\s*,\s*(['"])\.\2\s*\)/.test(rawLine)
            || /replace\s*\(\s*\/,\/g?\s*,\s*(['"])\.\1\s*\)/.test(rawLine);
          findings.push({
            at,
            why: swaps
              ? `character class ${c} keeps both separators and the line swaps "," for "." — "1.250,00" becomes "1.250.00", which parseFloat reads as 1.25`
              : `character class ${c} keeps BOTH separators but the line does not normalise "," to "." — parseFloat stops at the comma, so "1,5" parses as 1`,
            line: line.trim().slice(0, 110),
          });
          return;
        }
      }

      // --- 3: a bare parse of an obviously-money identifier ----------------
      // A written reason on the line, or in the comment block just above it
      // (which is where a reason long enough to be worth reading has to go).
      if (/numeric-ok:/.test(line) || rawLines.slice(Math.max(0, idx - 4), idx).some((l) => /numeric-ok:/.test(l))) return;
      const bare = line.match(/\b(parseFloat|parseInt|Number)\s*\(\s*([A-Za-z_$][\w$.]*)\s*[),]/);
      if (bare) {
        const arg = bare[2];
        if (!isMoneyIdentifier(arg)) return;
        // Already going through the safe parser, or reading a number back out.
        //
        // `Number(x.y)` used to be exempt here as "reading a NUMBER back out of
        // a typed object" — but `purchasePriceField.value` has exactly that
        // shape and is a STRING the member typed, so the exemption hid
        // `Number(purchasePriceField.value)` in add-manual: the field validated
        // "12,50" and then saved NaN (2026-09-16). An object field is only
        // exempt when its name says it is not money, which isMoneyIdentifier
        // has already decided by the time we get here.
        if (/parseMoney|toFixed/.test(line)) return;
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
// The old advice here WAS the bug in miniature: `.replace(',', '.')` turns a
// typed "1.250,00" into 1.25 (it strips nothing and swaps only the first
// separator). parseMoney treats the LAST separator as the decimal point.
console.log("  Safe form: parseMoney(value) from src/lib/format.ts — it handles 12,50 AND 1.250,00");
process.exit(1);
