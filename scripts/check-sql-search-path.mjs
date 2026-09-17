#!/usr/bin/env node
/**
 * A function's search_path is a LIST of schemas, never one quoted string.
 *
 *   SET search_path = public, pg_temp          ✓ two schemas
 *   SET search_path TO 'public', 'pg_temp'     ✓ two schemas
 *   SET search_path TO 'public, pg_temp'       ✗ ONE schema named "public, pg_temp"
 *   format('… SET search_path = %L', 'public, pg_temp')   ✗ the same, via %L
 *
 * WHY (2026-09-17): 20260424_security_advisor_bulk_C_and_A.sql used the %L form
 * (its header says on 410 functions). The quoted schema does not exist, so every
 * unqualified name inside those functions stops resolving. On 2026-09-17,
 * listing blocked members and the block check failed in production with
 * `relation "user_blocks" does not exist`, and blocking itself cannot resolve
 * its tables — behind a green security advisor, because a pinned path of ANY
 * value satisfies the linter.
 * Fixed by 20260917b_fix_quoted_search_path.sql.
 *
 * Postgres gives no error when the path is written: the mistake only shows up
 * when the function runs, and only in functions that use a bare name.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const DIR = join(ROOT, 'supabase', 'migrations');

// Superseded by 20260917b_fix_quoted_search_path.sql, which runs after them and
// re-pins every function they touched. Kept as history, never re-edited — and
// the gate FAILS if an entry stops matching, so this list cannot outlive its reason.
const HISTORICAL = new Map([
  ['20260424_security_advisor_bulk_C_and_A.sql', 'the %L bulk pin that caused it'],
  ['20260424_partition_price_history.sql', 'copied the quoted spelling by hand'],
  ['20260424_partition_price_predictions.sql', 'copied the quoted spelling by hand'],
  ['20260814g_fix_refresh_core_mvs.sql', 'copied the quoted spelling by hand'],
]);
const FIX = '20260917b_fix_quoted_search_path.sql';

/** Strip comments, keeping newlines so line numbers still agree. */
const stripSql = (sql) => sql
  .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
  .replace(/--[^\n]*/g, '');

// One quoted literal holding a comma, straight after search_path = / TO.
const QUOTED_LIST = /search_path\s*(?:=|\bto\b)\s*'[^']*,[^']*'/gi;
// A format() string that sets search_path through %L — %L always quotes its
// argument as ONE literal, whatever the argument is.
const VIA_L = /format\s*\(\s*'[^']*search_path\s*(?:=|\bto\b)\s*%L/gi;

const files = readdirSync(DIR).filter((f) => f.endsWith('.sql')).sort();
const findings = [];
const matchedHistorical = new Set();

for (const file of files) {
  const sql = stripSql(readFileSync(join(DIR, file), 'utf8'));
  for (const re of [QUOTED_LIST, VIA_L]) {
    for (const m of sql.matchAll(re)) {
      if (HISTORICAL.has(file)) { matchedHistorical.add(file); continue; }
      const line = sql.slice(0, m.index).split('\n').length;
      findings.push(`${file}:${line}  ${m[0].replace(/\s+/g, ' ').slice(0, 90)}`);
    }
  }
}

const stale = [...HISTORICAL.keys()].filter((f) => !matchedHistorical.has(f));
if (!files.includes(FIX)) findings.push(`${FIX} is missing — the historical allowlist is only safe while it runs after them`);
for (const f of stale) findings.push(`allowlist entry ${f} no longer matches — remove it`);

if (findings.length) {
  console.error(`✗ sql search_path — ${findings.length} problem(s):`);
  for (const f of findings) console.error(`   ${f}`);
  console.error('\n   Write the list as SQL: SET search_path = public, pg_temp');
  console.error("   (or 'public', 'pg_temp' — one quoted string per schema). Never %L.");
  process.exit(1);
}
console.log(`✓ sql search_path — ${files.length} migrations, no quoted multi-schema path outside the ${HISTORICAL.size} superseded files.`);
