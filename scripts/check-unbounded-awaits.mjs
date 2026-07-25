#!/usr/bin/env node
/**
 * Fails when a supabase-js call is awaited without a timeout.
 *
 * Why this exists: supabase-js has NO per-request timeout. A query fired while
 * the auth session is hydrating does not fail fast — it stalls behind the auth
 * lock. Any such await sitting between a spinner going up and coming down pins
 * that spinner forever: nothing saved, no error, nothing logged.
 *
 * That shipped three times (items skeleton, home skeleton, add-manual "Saving…")
 * and each was found only after Merle hit it. Judgment-triage is what let the
 * edit-save path through, so this check is mechanical: every call site is either
 * bounded or listed in the allowlist WITH A REASON. There is no third option.
 *
 * Auth ops are the deliberate exception. `withTimeout` is Promise.race, which
 * abandons rather than cancels; a second concurrent auth op can trip Supabase's
 * refresh-token reuse detection and REVOKE the session (docs/AUTH_AND_WEB_DEPLOY.md).
 * Those are allowlisted, not "fixed".
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const SCAN_DIRS = ['app', 'src'];
const ALLOWLIST_PATH = join(ROOT, 'scripts', 'unbounded-await-allowlist.json');

/** `await supabase.foo` / `await supabase\n  .foo` / `await this.client.foo` */
const AWAIT_RE = /await\s+(?:supabase|this\.client)\s*\.\s*([a-zA-Z_]+)/g;

function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === '__tests__' || entry.startsWith('.')) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(entry)) out.push(full);
  }
  return out;
}

function lineOf(src, index) {
  return src.slice(0, index).split('\n').length;
}

// ── Invariant 1: the central bound must still be installed ────────────────
// Every .from()/.rpc() is bounded by installRequestTimeouts() in the client.
// If that call is ever removed, all 59 PostgREST sites silently become
// unbounded again, so assert it here rather than trusting it.
const clientSrc = readFileSync(join(ROOT, 'src', 'lib', 'supabase.ts'), 'utf8');
if (!/installRequestTimeouts\s*\(\s*createClient/.test(clientSrc)) {
  console.error('\n[unbounded-await] FAIL — src/lib/supabase.ts no longer wraps');
  console.error('createClient() in installRequestTimeouts(). Every .from()/.rpc()');
  console.error('call in the app just became unbounded again.\n');
  process.exit(1);
}

const allowlist = JSON.parse(readFileSync(ALLOWLIST_PATH, 'utf8'));
const allowed = new Map(allowlist.entries.map((e) => [`${e.file}:${e.symbol}`, e.reason]));

const findings = [];
const usedAllowlistKeys = new Set();

for (const dir of SCAN_DIRS) {
  for (const file of walk(join(ROOT, dir))) {
    const rel = relative(ROOT, file);
    const src = readFileSync(file, 'utf8');
    for (const m of src.matchAll(AWAIT_RE)) {
      const symbol = m[1];
      // Bounded if this await is the withTimeout call itself, i.e. the
      // preceding text on the line/statement mentions withTimeout.
      const stmtStart = src.lastIndexOf('\n', m.index) + 1;
      const prefix = src.slice(Math.max(0, stmtStart - 200), m.index);
      if (/withTimeout\s*\($/.test(prefix.trimEnd()) || /withTimeout/.test(src.slice(stmtStart, m.index))) {
        continue;
      }
      // .from()/.rpc() are bounded centrally by the client wrapper asserted
      // above, so an unwrapped await on them is fine. auth.* is NOT wrapped —
      // Promise.race abandons rather than cancels, and a second concurrent auth
      // op can trip refresh-token reuse detection and REVOKE the session. Each
      // one therefore needs an explicit, written reason.
      if (symbol !== 'auth') continue;

      const key = `${rel}:${symbol}`;
      if (allowed.has(key)) {
        usedAllowlistKeys.add(key);
        continue;
      }
      findings.push({ file: rel, line: lineOf(src, m.index), symbol, key });
    }
  }
}

const stale = allowlist.entries
  .map((e) => `${e.file}:${e.symbol}`)
  .filter((k) => !usedAllowlistKeys.has(k));

if (findings.length === 0 && stale.length === 0) {
  console.log(`[unbounded-await] PASS — client bound installed; ${allowed.size} auth call site(s) allowlisted`);
  process.exit(0);
}

if (findings.length) {
  console.error(`\n[unbounded-await] FAIL — ${findings.length} unallowlisted supabase.auth await(s):\n`);
  for (const f of findings) {
    console.error(`  ${f.file}:${f.line}  await supabase.${f.symbol}(...)`);
  }
  console.error(`\nFix: wrap in withTimeout(...) from '@/lib/withTimeout', log timeouts with`);
  console.error(`logger.error (info/warn are STRIPPED in release builds).`);
  console.error(`If it is an auth op that must NOT be raced, add it to`);
  console.error(`scripts/unbounded-await-allowlist.json with a reason.\n`);
}

if (stale.length) {
  console.error(`[unbounded-await] Stale allowlist entries (call site gone — delete them):`);
  for (const k of stale) console.error(`  ${k}`);
  console.error('');
}

process.exit(1);
