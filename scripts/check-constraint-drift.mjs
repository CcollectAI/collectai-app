#!/usr/bin/env node
/**
 * Fails when code writes a literal a CHECK constraint would reject.
 *
 * A CHECK narrower than the code's allow-list is a silent dead feature: the
 * write raises 23514 deep in a handler, gets swallowed or logged as a generic
 * error, and the feature simply never works for that value. Everything else
 * looks fine — the table exists, the column exists, the type matches, the
 * endpoint returns 200 for the values that DO pass.
 *
 * Grep cannot answer this: it needs the constraint's literal set from the DB
 * compared against the literals the code actually writes. schema.lock.json
 * already carries `checks[table.col]`, so this runs offline.
 *
 * Deliberately conservative. It only reports a literal when it can see the
 * column being assigned that literal near a mention of the table, and only for
 * CHECKs of the `col = ANY (ARRAY[...])` form. False positives here would train
 * the reader to ignore the check, which is worse than missing a case.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const LOCK = JSON.parse(readFileSync(join(ROOT, 'scripts', 'schema.lock.json'), 'utf8'));

/** table.col -> Set(allowed literals) for `col = ANY (ARRAY['a','b'])` CHECKs. */
const allowed = new Map();
for (const [key, exprs] of Object.entries(LOCK.checks ?? {})) {
  const text = Array.isArray(exprs) ? exprs.join(' ') : String(exprs);
  const arr = text.match(/ANY\s*\(\s*ARRAY\[(.*?)\]/s);
  if (!arr) continue;
  const lits = [...arr[1].matchAll(/'([^']+)'::text/g)].map((m) => m[1]);
  if (lits.length) allowed.set(key, new Set(lits));
}

function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e === '__pycache__' || e.startsWith('.')) continue;
    const f = join(dir, e);
    if (statSync(f).isDirectory()) walk(f, out);
    else if (/\.(ts|tsx|py)$/.test(e)) out.push(f);
  }
  return out;
}

const files = [];
for (const d of ['app', 'src', 'server']) {
  try { walk(join(ROOT, d), files); } catch { /* dir may not exist */ }
}

const findings = [];
// Require the table and the column assignment to occur in the SAME statement.
// The first version matched a literal anywhere in a file that merely mentioned
// the table, so `purchase_mandates WHERE status='active'` was blamed on
// catalog_suggestions -- 33 findings, all false. A gate that cries wolf 33
// times is one nobody reads, which is worse than no gate.
for (const [key, allow] of allowed) {
  const [table, col] = key.split('.');
  if (!table || !col) continue;
  // FROM/INTO/UPDATE <table> ... <col> = 'literal', within one statement.
  const stmt = new RegExp(
    `(?:FROM|INTO|UPDATE)\\s+(?:public\\.)?${table}\\b[^;]{0,300}?\\b${col}\\s*=\\s*'([a-z0-9_\\-]{2,40})'`,
    'gis',
  );
  for (const file of files) {
    if (file.includes('__tests__') || file.includes('/tests/')) continue;
    const src = readFileSync(file, 'utf8');
    if (!src.includes(table)) continue;
    for (const m of src.matchAll(stmt)) {
      if (allow.has(m[1])) continue;
      findings.push({
        file: relative(ROOT, file),
        line: src.slice(0, m.index).split('\n').length,
        key, val: m[1], allow: [...allow].join(', '),
      });
    }
  }
}

if (!findings.length) {
  console.log(`[constraint-drift] PASS — no literal conflicts with ${allowed.size} CHECK constraint(s)`);
  process.exit(0);
}

console.error(`\n[constraint-drift] FAIL — ${findings.length} literal(s) a CHECK would reject:\n`);
for (const f of findings) {
  console.error(`  ${f.file}:${f.line}`);
  console.error(`    writes ${f.key} = '${f.val}'`);
  console.error(`    CHECK allows: ${f.allow}\n`);
}
console.error('A rejected write raises 23514 deep in a handler and is usually');
console.error('swallowed — the feature silently never works for that value.\n');
process.exit(1);
