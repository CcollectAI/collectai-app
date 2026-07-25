#!/usr/bin/env node
/**
 * One entry point for every mechanical check.
 *
 * Written 2026-07-25 after a run of ad-hoc greps: each answered a real question
 * once, printed, and vanished. A throwaway scan has no value the day after it
 * runs — the point of a check is not "it found nothing today", it is "it fails
 * the day this breaks". Anything worth scanning once belongs here.
 *
 * Local checks run directly. DB checks need the live schema (they ask questions
 * about VALUES, which no grep can answer) and run over ssh against EC2; they are
 * skipped, not failed, when the host is unreachable — a skipped check is
 * reported as SKIP so it can never be mistaken for a pass.
 *
 * Usage:
 *   npm run audit:all           local checks only (fast, offline)
 *   npm run audit:all -- --db   include the live-database checks
 */
import { execSync } from 'node:child_process';

const WITH_DB = process.argv.includes('--db');
const SSH = 'ssh -o ConnectTimeout=15 collectai';
const REMOTE_PY = 'cd /opt/collectors/server && set -a && . /opt/collectors/.env && set +a && /opt/collectors/.venv/bin/python';

/** @type {{name:string, cmd:string, db?:boolean, why:string}[]} */
const CHECKS = [
  {
    name: 'unbounded-await',
    cmd: 'node scripts/check-unbounded-awaits.mjs',
    why: 'a supabase call with no timeout pins a spinner forever, silently',
  },
  {
    name: 'silent-failures',
    cmd: 'node scripts/check-silent-failures.mjs --strict',
    why: 'demo data, capped aggregates, unchecked writes, swallowed errors',
  },
  {
    name: 'fe-api-drift',
    cmd: 'python3 scripts/audit_fe_api_drift.py',
    why: 'the FE calling an endpoint the backend does not define (404 -> empty state)',
  },
  {
    name: 'dead-nav-targets',
    cmd: 'node scripts/check-dead-nav.mjs',
    why: 'a router.push to a route with no file — a button that goes nowhere',
  },
  {
    name: 'constraint-drift',
    cmd: 'node scripts/check-constraint-drift.mjs',
    why: 'code using a literal a CHECK rejects — writes 23514, reads silently return 0',
  },
  {
    name: 'upsert-targets',
    cmd: 'node scripts/check-upsert-targets.mjs',
    why: 'ON CONFLICT naming columns with no unique key — 42P10, swallowed, row never written',
  },
  {
    name: 'item-writers',
    cmd: 'python3 server/scripts/audit_item_writers.py',
    why: 'an INSERT INTO items with no canonical_key — the item can never be priced',
  },
  {
    name: 'canonical-key-resolution',
    cmd: `${SSH} '${REMOTE_PY} scripts/probe_canonical_key_resolution.py'`,
    db: true,
    why: 'the add paths RESOLVING a key, not just naming the column (values, not structure)',
  },
  {
    name: 'env-coverage',
    cmd: `${SSH} '${REMOTE_PY} scripts/audit_env_coverage.py'`,
    db: true,
    why: 'a credential read with no default but empty in prod — the client silently degrades',
  },
  {
    name: 'fe-rpc-contract',
    cmd: `${SSH} '${REMOTE_PY} scripts/audit_fe_rpc_contract.py'`,
    db: true,
    why: 'a supabase.rpc() the FE calls that is missing or ungranted — 404/42501, swallowed',
  },
  {
    name: 'account-deletion',
    cmd: `${SSH} '${REMOTE_PY} scripts/audit_account_deletion.py'`,
    db: true,
    why: 'user data surviving DELETE /account while it reports success',
  },
  {
    name: 'rls-coverage',
    cmd: `${SSH} '${REMOTE_PY} scripts/audit_rls_coverage.py'`,
    db: true,
    why: 'RLS off (data leak) or on with no policies (silent deny-all)',
  },
  {
    name: 'key-overlap',
    cmd: `${SSH} '${REMOTE_PY} scripts/audit_key_overlap.py'`,
    db: true,
    why: 'a join whose two sides share no values — valid SQL, zero rows, no error',
  },
  {
    name: 'orphan-tables',
    cmd: `${SSH} '${REMOTE_PY} scripts/audit_orphan_tables.py'`,
    db: true,
    why: 'a table read by code that nothing writes — a feature that cannot work',
  },
];

const results = [];
for (const check of CHECKS) {
  if (check.db && !WITH_DB) {
    results.push({ ...check, status: 'SKIP', detail: 'needs --db' });
    continue;
  }
  process.stdout.write(`  running ${check.name}… `);
  try {
    const out = execSync(check.cmd, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 300_000 });
    results.push({ ...check, status: 'PASS', detail: '', out });
    console.log('PASS');
  } catch (e) {
    const out = `${e.stdout ?? ''}${e.stderr ?? ''}`;
    // ssh itself failing (host down) is a SKIP, not a finding — reporting it as
    // a failure would train the reader to ignore the whole suite.
    const unreachable = /ssh:|Connection (refused|timed out)|Could not resolve/i.test(out);
    results.push({ ...check, status: unreachable ? 'SKIP' : 'FAIL', detail: unreachable ? 'host unreachable' : '', out });
    console.log(unreachable ? 'SKIP (host unreachable)' : 'FAIL');
  }
}

console.log('\n=== audit summary ===\n');
const pad = Math.max(...results.map((r) => r.name.length));
for (const r of results) {
  const mark = r.status === 'PASS' ? 'PASS' : r.status === 'SKIP' ? 'SKIP' : 'FAIL';
  console.log(`  ${mark}  ${r.name.padEnd(pad)}  ${r.detail || r.why}`);
}

const failed = results.filter((r) => r.status === 'FAIL');
const skipped = results.filter((r) => r.status === 'SKIP');
if (failed.length) {
  console.log(`\n--- output from ${failed.length} failing check(s) ---`);
  for (const f of failed) {
    console.log(`\n## ${f.name}\n${(f.out || '').trim().slice(0, 4000)}`);
  }
}
console.log(
  `\n${results.length - failed.length - skipped.length} passed, ${failed.length} failed, ${skipped.length} skipped` +
    (skipped.length && !WITH_DB ? '  (re-run with --db for the live-database checks)' : ''),
);
process.exit(failed.length ? 1 : 0);
