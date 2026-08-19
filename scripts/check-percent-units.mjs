#!/usr/bin/env node
/**
 * Gate: a field named `*_pct` may be a FRACTION or a PERCENT, and the client
 * has to know which.
 *
 * Why this exists
 * ---------------
 * Found 2026-08-19 on the Home category breakdown.
 * `/analytics/portfolio/category-breakdown` returns
 * `pct_of_portfolio = round(val / total_value, 4)` -- a fraction, 0..1, pinned
 * that way by its own server test (`== 0.625`). Home assigned it straight into
 * `percentage`, which `CategoryBreakdownSection` renders BOTH as
 * `percentage.toFixed(0)}%` AND as a bar `width: ${percentage}%`.
 *
 * Measured on prod: pokemon held 51.6% of the portfolio and drew "1%";
 * one_piece_tcg held 48.4% and drew "0%"; every bar collapsed to its 2% floor.
 * The chart read as flat and empty while every number behind it was correct.
 *
 * BOTH SIDES WERE SELF-CONSISTENT AND BOTH WERE TESTED. The server has a test
 * pinning the fraction; the component renders whatever it is handed. Only the
 * JOIN between them was wrong, which is exactly why nothing caught it
 * (learning_verify_the_display_seam_not_isolated_units).
 *
 * The root cause is that the SAME SUFFIX means both things across this API:
 *
 *   FRACTION (0..1)                    PERCENT (0..100)
 *   pct_of_portfolio                   pct_of_total     (grading_router)
 *   share_pct        (insights)        positive_pct     (p2p_offers)
 *   change_1d_pct    (portfolio)       change_7d_pct    (portfolio!)
 *   change_pct       (insights)        completion_pct   (set/collections)
 *   gain_pct         (trends)          signup_to_paid_pct
 *
 * `change_1d_pct` and `change_7d_pct` sit in the SAME router with DIFFERENT
 * units. No amount of care at the call site fixes that; only a check does.
 *
 * What it checks
 * --------------
 * 1. Every server assignment to a `*pct*` / `*percent*` field is classified
 *    FRACTION or PERCENT by whether a literal 100 appears in the expression.
 * 2. For every FRACTION field that the client actually reads, the read must be
 *    scaled -- a `* 100` within a few lines -- or be listed in ALLOWLIST with
 *    a reason.
 * 3. Reads inside comments do not count. A comment saying "this is a fraction"
 *    is what an earlier hand-audit was fooled by.
 *
 * Exits non-zero on any unscaled read of a fraction field.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname;
const SERVER = join(ROOT, 'server', 'app');
const CLIENT = [join(ROOT, 'src'), join(ROOT, 'app')];

/**
 * Fields a client legitimately reads without scaling, each with the reason.
 * A bare name is not enough: say WHY, or the next reader assumes it was
 * checked when it was only added to make the gate quiet.
 */
const ALLOWLIST = new Map([
  // Deliberately EMPTY. `pct_of_portfolio` was listed here in the first draft
  // "because its name also appears in the explanatory header" -- which would
  // have exempted the one field this gate exists for, so a regression on it
  // would have passed silently. The header lines are skipped as comments and
  // __tests__ is skipped wholesale, so no exemption is needed. Proven by
  // deleting the * 100 and watching this go red.
]);

/**
 * A FIELD name, never a local variable and never a bare `pct`.
 *
 * v1 of this gate matched any name containing "pct", which picked up `pct` out
 * of a Telegram f-string (`{x:.0f}%</b>`) and then substring-matched every
 * `pct` in the client -- 130 findings, all noise. This repo has already
 * measured and REJECTED one sweep for exactly that
 * (learning_check_narrower_than_code_is_invisible_to_fe), so the rule is:
 * a name must be qualified (`share_pct`, `pct_of_portfolio`), never the bare
 * word, and client reads match on a WORD BOUNDARY.
 */
const NAME_RE = /^(?=.{6,40}$)[a-z][a-z0-9_]*(_pct|_percent|_percentage)$|^pct_[a-z][a-z0-9_]*$|^percent_[a-z][a-z0-9_]*$/;

function walk(dir, ext, out = []) {
  let entries;
  try { entries = readdirSync(dir); } catch { return out; }
  for (const e of entries) {
    if (e === 'node_modules' || e === '__pycache__' || e.startsWith('.')) continue;
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p, ext, out);
    else if (ext.some((x) => p.endsWith(x))) out.push(p);
  }
  return out;
}

/** Drop Python `#` and JS `//` line comments, and `--` inside SQL strings. */
function codeOnly(src) {
  return src
    .split('\n')
    .filter((l) => {
      const t = l.trim();
      return !(t.startsWith('#') || t.startsWith('//') || t.startsWith('--') || t.startsWith('*'));
    })
    .join('\n');
}

// ── 1. classify every server-side percent-ish field ────────────────────────
const fractions = new Map();     // name -> "file:line  expr"
const percents = new Set();
const unclassified = new Map();  // name -> "file:line  expr" — REPORTED, not hidden

for (const file of walk(SERVER, ['.py'])) {
  const lines = codeOnly(readFileSync(file, 'utf8')).split('\n');
  lines.forEach((line, i) => {
    // `name=expr,`  |  `name = expr`  |  `"name": expr,`
    const m = line.match(/(?:^|[\s{(,])(?:"|')?([a-z][a-z0-9_]*)(?:"|')?\s*[:=]\s*([^=].*?),?\s*$/);
    if (!m) return;
    const [, name, expr] = m;
    if (!NAME_RE.test(name)) return;
    // Inside a format string, not an assignment: `f"...{x:.0f}%..."` ends in a
    // quote and carries braces. This is how v1 picked up a Telegram message.
    if (/["'].*["']\s*$/.test(expr) && /[{}%]/.test(expr)) return;
    if (expr.includes('}')) return;
    // A type annotation (`pct_of_total: float = 0.0`) declares nothing about
    // the unit -- skip it rather than classify a default of 0.0 as a fraction.
    if (/^\s*(float|int|Optional|List|str|bool)\b/.test(expr)) return;
    const where = `${relative(ROOT, file)}:${i + 1}  ${expr.trim()}`;

    // ORDER MATTERS, and v1 got it backwards. "contains 100 => percent" marked
    // `change_pct=round(delta_pct_7d / 100.0, 4)` as a PERCENT when dividing BY
    // 100 is exactly what turns a percent INTO a fraction. Test the division
    // first.
    if (/\/\s*100(\.0)?\b/.test(expr)) { fractions.set(name, where); return; }
    if (/\*\s*100(\.0)?\b|\b100(\.0)?\s*\*/.test(expr)) { percents.add(name); return; }
    if (expr.includes('/')) { fractions.set(name, where); return; }  // a bare ratio

    // Everything else -- `round(share, 4)`, `float(row["x"])` -- carries the
    // unit somewhere this script cannot see. v1 dropped these on the floor via
    // an `if (!/[/*]/) return`, which silently lost `share_pct` and
    // `change_1d_pct`: two of the three fields that DO need scaling. Reported
    // instead, because "3 fields checked" with no denominator reads as full
    // coverage when it is really a regex that stopped matching.
    if (!percents.has(name) && !fractions.has(name)) unclassified.set(name, where);
  });
}

// A name computed BOTH ways somewhere is still a fraction somewhere, so it
// stays in the fraction set -- the client cannot tell which endpoint it came
// from either, and that ambiguity is itself the finding.

// ── 2. every client read of a fraction field must scale it ─────────────────
const failures = [];
const clientFiles = CLIENT.flatMap((d) => walk(d, ['.ts', '.tsx']));

for (const [name, origin] of fractions) {
  for (const file of clientFiles) {
    const rel = relative(ROOT, file);
    if (rel.includes('__tests__')) continue;
    const raw = readFileSync(file, 'utf8');
    const word = new RegExp(`\\b${name}\\b`);
    if (!word.test(raw)) continue;
    const lines = raw.split('\n');
    lines.forEach((line, i) => {
      const t = line.trim();
      if (!word.test(line)) return;
      if (t.startsWith('//') || t.startsWith('*') || t.startsWith('/*')) return;
      // A type/interface declaration READS nothing -- it only names a field.
      // The line-start-only version of this missed inline members
      // (`{ name: string; change_pct: number }[]`) and reported three of them.
      // Anchored on THE NAME being followed by a TYPE, so an assignment whose
      // right-hand side merely mentions the field is still treated as a read.
      if (new RegExp(`\\b${name}\\??\\s*:\\s*(number|string|boolean|null|z\\.|\\{)`).test(t)) return;
      // Scaled here, or within the next two lines (multi-line ternaries).
      const window = lines.slice(i, i + 3).join(' ');
      if (/\*\s*100\b|100\s*\*/.test(window)) return;
      if (ALLOWLIST.has(name)) return;
      failures.push({ name, origin, at: `${rel}:${i + 1}`, line: t });
    });
  }
}

// ── report ────────────────────────────────────────────────────────────────
const fracList = [...fractions.keys()].sort();
// `--list` prints the classification. Coverage stated, not implied: "N fields
// checked" with no denominator reads as full coverage when it may be a regex
// that stopped matching.
if (process.argv.includes('--list')) {
  console.log('FRACTION (0..1):');
  for (const [n, o] of fractions) console.log(`  ${n.padEnd(22)} ${o}`);
  console.log('PERCENT (0..100):');
  for (const n of [...percents].sort()) console.log(`  ${n}`);
  console.log('UNCLASSIFIED — unit not visible at the assignment:');
  for (const [n, o] of unclassified) console.log(`  ${n.padEnd(22)} ${o}`);
}
if (failures.length === 0) {
  console.log(
    `[percent-units] PASS — ${fracList.length} fraction field(s) and ` +
    `${percents.size} percent field(s) classified; every client read of a ` +
    `fraction is scaled or explained.` +
    (unclassified.size
      ? ` ${unclassified.size} field(s) NOT classifiable from their assignment ` +
        `(run with --list): ${[...unclassified.keys()].sort().join(', ')}.`
      : ''));
  process.exit(0);
}

console.error('[percent-units] FAIL — a fraction (0..1) is read as a percent (0..100)\n');
for (const f of failures) {
  console.error(`  ${f.at}`);
  console.error(`    reads   ${f.name}  without a * 100`);
  console.error(`    server  ${f.origin}`);
  console.error(`    line    ${f.line}\n`);
}
console.error(
  'Multiply by 100 at the seam, or add the field to ALLOWLIST in this script\n' +
  'WITH A REASON. See docs/ARCHITECTURE.md "pct_of_portfolio is a FRACTION".');
process.exit(1);
