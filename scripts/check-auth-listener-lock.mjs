#!/usr/bin/env node
/**
 * No Supabase work may be AWAITED inside an onAuthStateChange callback.
 *
 * GoTrueClient runs these callbacks while it holds the auth lock (processLock,
 * load-bearing — see src/lib/supabase.ts), and it waits for every subscriber
 * before releasing it. Any `supabase.from(...)` / `.rpc(...)` needs the session,
 * so it queues on that same lock: the callback waits on a lock it is holding,
 * and every request in the app stalls until a timeout breaks the cycle.
 *
 * Fixed once in AuthProvider (setTimeout(0), measured: "profile hydrate failed
 * after 6011ms" on every cold start). It came back on 2026-09-24 in a SECOND
 * copy of the same logic, src/hooks/useAuth.ts: an `async` listener awaiting a
 * profiles read. On Android every cold start into a profile stalled all
 * Supabase requests ~15 s and showed "Couldn't load this profile".
 *
 * Rule: the callback is not `async`, and contains no `await` outside a
 * `setTimeout(...)` (which runs after the callback returns and the lock is free).
 *
 *   node scripts/check-auth-listener-lock.mjs      # exit 1 on a violation
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname;
const SKIP = new Set(['node_modules', '__tests__', '__mocks__', '.git', 'ios', 'android']);
function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    if (SKIP.has(e)) continue;
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(ts|tsx)$/.test(e) && !/\.test\.tsx?$/.test(e)) out.push(p);
  }
  return out;
}
const blank = (s) => s
  .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
  .replace(/(^|[^:'"`])\/\/[^\n]*/g, (m, pre) => pre + ' '.repeat(m.length - pre.length));

/** Index of the paren that closes the one opening at `open`. */
function closeParen(src, open) {
  let depth = 0;
  for (let i = open; i < src.length; i++) {
    if (src[i] === '(') depth++;
    else if (src[i] === ')' && --depth === 0) return i;
  }
  return -1;
}
/** Remove every setTimeout(...) call from a span: work there runs after the lock is released. */
function dropDeferred(span) {
  let out = span;
  for (let i = out.search(/\bsetTimeout\s*\(/); i >= 0; i = out.search(/\bsetTimeout\s*\(/)) {
    const open = out.indexOf('(', i);
    const close = closeParen(out, open);
    if (close < 0) break;
    out = out.slice(0, i) + ' '.repeat(close + 1 - i) + out.slice(close + 1);
  }
  return out;
}

const failures = [];
let listeners = 0;
for (const file of [...walk(join(ROOT, 'app')), ...walk(join(ROOT, 'src'))]) {
  const src = blank(readFileSync(file, 'utf8'));
  const re = /\bonAuthStateChange\s*\(/g;
  let m;
  while ((m = re.exec(src)) !== null) {
    const open = src.indexOf('(', m.index);
    const close = closeParen(src, open);
    if (close < 0) continue;
    listeners++;
    const span = src.slice(open + 1, close);
    const line = src.slice(0, m.index).split('\n').length;
    const where = `${relative(ROOT, file)}:${line}`;
    if (/^\s*[A-Za-z_$][\w$.]*\s*$/.test(span)) {
      failures.push(`${where}  the callback is passed by NAME — write it inline so this gate can read it`);
      continue;
    }
    if (/^\s*async\b/.test(span)) {
      failures.push(`${where}  the callback is \`async\` — it runs inside the auth lock`);
      continue;
    }
    if (/\bawait\b/.test(dropDeferred(span))) {
      failures.push(`${where}  \`await\` inside the callback — defer it with setTimeout(() => …, 0)`);
    }
  }
}

if (listeners === 0) {
  console.error('[auth-listener-lock] FAIL — found no onAuthStateChange listener at all; the scan is broken.');
  process.exit(1);
}
if (failures.length) {
  console.error('[auth-listener-lock] FAIL — Supabase work awaited inside the auth lock:\n');
  for (const f of failures) console.error('  ' + f);
  console.error('\nThe callback holds GoTrue\'s lock until it returns; a query awaited there waits on that lock.');
  process.exit(1);
}
console.log(`[auth-listener-lock] PASS — ${listeners} onAuthStateChange listener(s), none awaits inside the lock.`);
