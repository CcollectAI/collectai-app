#!/usr/bin/env node
/**
 * Fails when ON CONFLICT names columns with no matching unique constraint.
 *
 * Postgres rejects such an upsert at runtime with 42P10 ("no unique or
 * exclusion constraint matching the ON CONFLICT specification"). In this
 * codebase that lands inside a worker loop or a request handler where the
 * except/catch swallows it, so the write silently never happens — the row
 * simply never appears and the feature looks empty rather than broken.
 *
 * schema.lock.json's own header says it: "uniques[table] — unique-key column
 * tuples (constraint or unique index); UPSERT/ON CONFLICT depends on these
 * staying put". This is the check that makes that sentence enforceable, and it
 * runs offline.
 *
 * A DROP or a rename of a unique index is invisible to every other gate: the
 * table still exists, the columns still exist, the SQL still parses.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const LOCK = JSON.parse(readFileSync(join(ROOT, 'scripts', 'schema.lock.json'), 'utf8'));
const UNIQUES = LOCK.uniques ?? {};

// ON CONFLICT accepts any unique key whose column SET matches, order-insensitive.
const keyOf = (cols) => [...cols].map((c) => c.trim().toLowerCase()).sort().join(',');

const uniqueSets = new Map();
for (const [table, tuples] of Object.entries(UNIQUES)) {
  uniqueSets.set(table, new Set((tuples ?? []).map(keyOf)));
}

function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e === '__pycache__' || e.startsWith('.')) continue;
    const f = join(dir, e);
    if (statSync(f).isDirectory()) walk(f, out);
    else if (/\.(py|ts|tsx|sql)$/.test(e)) out.push(f);
  }
  return out;
}

const files = [];
for (const d of ['server', 'src', 'app']) {
  try { walk(join(ROOT, d), files); } catch { /* optional dir */ }
}

// INSERT INTO <table> ( ... ) ... ON CONFLICT ( <cols> )
const RE = /INSERT\s+INTO\s+(?:public\.)?([a-z_][a-z0-9_]*)\b[\s\S]{0,1200}?ON\s+CONFLICT\s*\(([^)]*)\)/gi;

const findings = [];
for (const file of files) {
  if (file.includes('__tests__') || file.includes('/tests/')) continue;
  const src = readFileSync(file, 'utf8').replace(/--[^\n]*/g, '');
  for (const m of src.matchAll(RE)) {
    const table = m[1].toLowerCase();
    const cols = m[2].split(',').map((c) => c.trim()).filter(Boolean);
    if (!cols.length) continue;
    // COALESCE(...) and other expressions in the conflict target need a matching
    // partial/expression index, which the lock does not model. Skip rather than
    // guess — a false positive costs more than a miss.
    if (m[2].includes('(')) continue;
    const known = uniqueSets.get(table);
    if (!known) continue;                       // table not in lock (view/new) — not our call
    if (known.has(keyOf(cols))) continue;       // matches a real unique key
    findings.push({
      file: relative(ROOT, file),
      line: src.slice(0, m.index).split('\n').length,
      table, cols: cols.join(', '),
      known: [...known].join('  |  ') || '(none)',
    });
  }
}

if (!findings.length) {
  console.log(`[upsert-targets] PASS — every ON CONFLICT matches a unique key (${uniqueSets.size} tables)`);
  process.exit(0);
}

console.error(`\n[upsert-targets] FAIL — ${findings.length} ON CONFLICT target(s) with no unique key:\n`);
for (const f of findings) {
  console.error(`  ${f.file}:${f.line}`);
  console.error(`    ON CONFLICT (${f.cols})  on  ${f.table}`);
  console.error(`    unique keys that exist: ${f.known}\n`);
}
console.error('Postgres raises 42P10 for these at runtime. Swallowed by the');
console.error('surrounding handler, the row just never gets written.\n');
process.exit(1);
