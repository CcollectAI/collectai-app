#!/usr/bin/env node
/**
 * The class register must be navigable, and rows that claim OPEN work must be
 * re-verified rather than recited.
 *
 * WHY: on 2026-09-20 four summary rows in docs/CLASS_SWEEPS.md were stale while
 * their own detail sections were correct and dated — H ("locale half open",
 * closed two days earlier), L ("~145 a11y labels", 9 left and all deliberate),
 * S ("one decision left: reports_count", dropped in migration 20260918b), and
 * G ("4 decisions for Merle", all four resolved). I recited G's four at Merle
 * several times that day and re-reported one of them as a NEW finding.
 *
 * The cause is structural, not carelessness: the detail section is edited by
 * whoever does the work; the one-line row is not. And the detail is stored in
 * THREE formats ("## X —", "## Class X —", and bold "**X —**" inside
 * "What is open"), so it is not reliably findable — which is what let the rows
 * drift unnoticed.
 *
 * This gate enforces the navigable half, which is mechanical, and LISTS the
 * open-claiming rows so a human re-verifies them. It deliberately does not try
 * to judge whether a row's prose agrees with its section — that needs reading.
 *
 *   node scripts/check-class-register.mjs           # exit 1 if a row has no detail
 *   node scripts/check-class-register.mjs --list    # also print open-claiming rows
 */
import { readFileSync } from 'node:fs';

const FILE = 'docs/CLASS_SWEEPS.md';
const lines = readFileSync(FILE, 'utf8').split('\n');

const ROW = /^\|\s*([A-Z]{1,2}(?:-[0-9])?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|\s*$/;
// all three shapes the register actually uses
const HEAD = /^#{2,4}\s+(?:Class\s+)?([A-Z]{1,2}(?:-[0-9])?)\s*[—–-]/;
const BOLD = /^\*\*([A-Z]{1,2}(?:-[0-9])?)\s*[—–-]/;
// rows closed by a commit alone, with no write-up — allowed, but named here so
// the exemption cannot outlive its reason (see "make allowlists fail when an
// entry goes stale" in this file's own method section).
const NO_WRITEUP = { B: '02ee84b', C: '02ee84b' };

const rows = new Map();
const detail = new Map();
lines.forEach((l, i) => {
  const r = ROW.exec(l);
  if (r && !/^-+$/.test(r[2])) rows.set(r[1], { line: i + 1, status: r[4] });
  const h = HEAD.exec(l) || BOLD.exec(l);
  if (h && !detail.has(h[1])) detail.set(h[1], i + 1);
});

const problems = [];
for (const [cls, { line }] of rows) {
  if (detail.has(cls)) continue;
  if (cls in NO_WRITEUP) {
    const sha = NO_WRITEUP[cls];
    if (!rows.get(cls).status.includes(sha)) {
      problems.push(`  row ${cls} (L${line}) is exempt from needing a write-up because it was ` +
                    `closed by ${sha}, but the row no longer cites that commit — re-check it`);
    }
    continue;
  }
  problems.push(`  row ${cls} (L${line}) has no detail section. Add one as "## ${cls} — <title>", ` +
                `so the row can be checked against it.`);
}
for (const cls of detail.keys()) {
  if (!rows.has(cls)) problems.push(`  section ${cls} (L${detail.get(cls)}) has no register row.`);
}

console.log(`class register: ${rows.size} rows, ${detail.size} detail sections`);
if (problems.length) {
  console.log(`\nFAIL — ${problems.length} row(s) cannot be checked against a write-up:\n`);
  console.log(problems.join('\n'));
  process.exit(1);
}

const OPEN = /\b(open|OPEN|decision|decisions|still|not swept|NOT swept|remain|inconclusive|INCONCLUSIVE|measured)\b/;
const claiming = [...rows].filter(([, v]) => OPEN.test(v.status) && !/^✅/.test(v.status.trim()));
console.log('PASS — every row has a findable write-up');
if (process.argv.includes('--list') && claiming.length) {
  console.log(`\n${claiming.length} row(s) CLAIM open work. Re-verify against the section before quoting them:`);
  for (const [cls, v] of claiming) {
    console.log(`  ${cls} (L${v.line} -> detail L${detail.get(cls) ?? '?'}): ${v.status.replace(/\s+/g, ' ').slice(0, 96)}`);
  }
}
