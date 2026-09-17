#!/usr/bin/env node
/**
 * One tap must not become two writes.
 *
 * A tap handler that `await`s a write and has no in-flight guard can run twice:
 * a double tap, or a slow network and an impatient member. What the second run
 * does depends on the server, and the failure is usually a LIE rather than a
 * duplicate — `purchase/deal/[dealId].handleDecline` had no guard and no
 * `disabled`, while its own sibling `handleConfirm` used `setConfirming`. The
 * server's decline is `UPDATE … WHERE status = ANY(_DECLINABLE_STATUSES)`, so
 * the second tap updates 0 rows, returns 404, and the member is told "Failed to
 * dismiss" about a deal that IS dismissed (class sweep I, docs/CLASS_SWEEPS.md).
 *
 * A finding is a handler that:
 *   - is named like a tap handler (`handleX` or `onX`), AND
 *   - awaits something that WRITES (create/update/delete/save/submit/confirm/
 *     decline/send/post/accept/block/…, or an api post/patch/put/delete, or a
 *     supabase insert/update/delete/upsert/rpc), AND
 *   - has no guard: no `if (<flag>) return`, no `set<Flag>(true)` before the
 *     await, no `<ref>.current` latch, and no `busy`/`saving`/`sending` state
 *     set in the same function.
 *
 * Not a finding: a handler whose FIRST act is an Alert/confirm (the member has
 * to answer before anything is written), an optimistic UI removal that takes
 * the control away, or a written reason on the line above:
 *     // double-tap-ok: <why a second run is harmless>
 *
 * Idempotent writes still deserve a guard — two identical PATCHes are wasted
 * requests and a racing UI — but they are NOT dangerous, so they are reported
 * as backlog (exit 0) unless --strict.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const STRICT = process.argv.includes('--strict');
const SCAN = ['app', 'src'];

const walk = (dir, out = []) => {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e === '__tests__' || e.startsWith('.')) continue;
    const f = join(dir, e);
    if (statSync(f).isDirectory()) walk(f, out);
    else if (/\.(ts|tsx)$/.test(e)) out.push(f);
  }
  return out;
};
const lineOf = (s, i) => s.slice(0, i).split('\n').length;

const WRITE_CALL = new RegExp(
  [
    // provider / api verbs
    String.raw`\bawait\s+[\w.]*\b(create|update|delete|remove|save|submit|confirm|decline|dismiss|send|post|accept|reject|block|unblock|archive|unarchive|mark|claim|cancel|redeem|purchase|list|unlist|follow|unfollow|rsvp|join|leave|invite|report)\w*\s*\(`,
    // raw http
    String.raw`\bawait\s+(?:collectorsApi|api|httpClient)\.(post|patch|put|del|delete)\s*\(`,
    // supabase
    String.raw`\bawait\s+supabase[\s\S]{0,80}?\.(insert|update|delete|upsert|rpc)\s*\(`,
  ].join('|'),
  'i',
);
// `list`/`mark` are in the verb list because listForSale / markRead are writes,
// but a plain read like `await listItems()` is not — require a non-read shape.
const READ_ONLY = /\bawait\s+[\w.]*\b(list|get|fetch|load|search|lookup|read)\w*\s*\(/i;

/**
 * A guard is recognised by the FLAG'S NAME, not a list of verbs I happened to
 * think of. The first version listed verbs and reported three false positives
 * — `setCreating(true)`, `setMarkingAllRead(true)`, and
 * `if (!project || togglingComplete) return` — which is the fastest way to make
 * a checker ignorable. A latch is any identifier that reads like one:
 *   togglingComplete, markingAllRead, creating, busy, saving, submitting,
 *   sendPending, inFlight, disabled, loading
 */
// CONTAINS, not endsWith: `restoringId` is a latch and ends in "Id" — testing
// the end of the name re-flagged app/archived.tsx after I "improved" this.
const FLAG_NAME = /(ing|busy|pending|inflight|disabled|loading|locked|lock|sent|done)/i;
const isFlag = (name) => FLAG_NAME.test(name.replace(/^set/, ''));

function hasGuard(body) {
  if (/double-tap-ok:/.test(body)) return true;
  // A ref LATCH must be both written and READ. `ref.current = true` on its own
  // stops nothing — found by mutating this gate: deleting the early return left
  // the assignment behind and the gate stayed green.
  for (const m of body.matchAll(/(\w+)\.current\s*=\s*true/g)) {
    if (new RegExp(`if\\s*\\([^)]*\\b${m[1]}\\.current`).test(body)) return true;
  }
  // `if (<anything mentioning a latch>) return`. The condition is read with a
  // BALANCED scan: `[^)]*` stopped at the first `)`, so
  // `if (deletingIdsRef.current.has(imageId)) return` did not match its own guard.
  for (const m of body.matchAll(/if\s*\(/g)) {
    let depth = 0, i = m.index + m[0].length - 1, close = -1;
    for (; i < body.length; i++) {
      if (body[i] === '(') depth++;
      else if (body[i] === ')' && --depth === 0) { close = i; break; }
    }
    if (close < 0) continue;
    if (!/^\s*(\{[^}]{0,120}?)?return\b/.test(body.slice(close + 1))) continue;
    const cond = body.slice(m.index + m[0].length, close).trim();
    // `if (x) return` on its own is a latch by position: a single bare
    // identifier guarding a writing handler is what every guarded site here does.
    if (/^!?\s*[A-Za-z_$][\w$.]*$/.test(cond) && !/^!/.test(cond)) return true;
    for (const id of cond.matchAll(/[A-Za-z_$][\w$]*/g)) {
      if (isFlag(id[0]) || /^can[A-Z]/.test(id[0])) return true;
    }
  }
  // `setX(true)` / `setX('sending')` where X reads like a latch
  for (const m of body.matchAll(/\b(set[A-Z]\w*)\s*\(\s*(true|['"](?:sending|saving|submitting|busy|working|posting|deleting|creating|pending)['"])\s*\)/g)) {
    if (isFlag(m[1])) return true;
  }
  return false;
}

// A confirmation dialog IS the guard: nothing is written until the member answers.
const ASKS_FIRST = /Alert\.alert|showConfirm|confirmDialog|ConfirmSheet/;

const findings = [];
for (const abs of SCAN.flatMap((d) => walk(join(ROOT, d)))) {
  const rel = relative(ROOT, abs);
  if (/\/mocks?\//.test(rel)) continue;
  const src = readFileSync(abs, 'utf8');

  // `const handleX = useCallback(async (…) => {` / `= async (…) => {`
  const re = /const\s+(handle\w+|on[A-Z]\w*)\s*=\s*(?:useCallback\s*\(\s*)?async\s*\(([^)]*)\)\s*=>\s*\{/g;
  for (const m of src.matchAll(re)) {
    const open = src.indexOf('{', m.index + m[0].length - 1);
    let depth = 0, end = -1;
    for (let i = open; i < src.length; i++) {
      if (src[i] === '{') depth++;
      else if (src[i] === '}' && --depth === 0) { end = i; break; }
    }
    if (end < 0) continue;
    const body = src.slice(open, end);
    const code = body.replace(/\/\/[^\n]*/g, '').replace(/\/\*[\s\S]*?\*\//g, '');
    if (!WRITE_CALL.test(code)) continue;
    // a handler that only reads
    const writes = code.match(WRITE_CALL);
    if (writes && READ_ONLY.test(writes[0])) continue;
    if (hasGuard(body) || ASKS_FIRST.test(code)) continue;
    // The reason sits in the contiguous comment block above the handler — the
    // WHOLE block, not one line: a reason worth writing runs to three lines, and
    // a one-line lookback silently ignored every one of them (the same bug
    // check-view-rls had with a 4-line window).
    const lines = src.slice(0, m.index).split('\n');
    let reason = '';
    for (let k = lines.length - 2; k >= 0; k--) {
      const t = lines[k].trim();
      if (t === '') { if (reason) break; continue; }
      if (!t.startsWith('//') && !t.startsWith('*') && !t.startsWith('/*')) break;
      reason = t + '\n' + reason;
    }
    if (/double-tap-ok:/.test(reason)) continue;
    findings.push({ at: `${rel}:${lineOf(src, m.index)}`, name: m[1], call: (writes?.[0] ?? '').trim().slice(0, 60) });
  }
}

if (findings.length) {
  console.error(`✗ double submit — ${findings.length} tap handler(s) write with no in-flight guard:`);
  for (const f of findings) console.error(`   ${f.at}  ${f.name}() — ${f.call}`);
  console.error('\n   Latch the handler (a state flag set before the await, or a ref),');
  console.error('   disable the control while it runs, or write');
  console.error('   `// double-tap-ok: <why a second run is harmless>` above it.');
  if (STRICT) process.exit(1);
  process.exit(0);
}
console.log('✓ double submit — every writing tap handler is guarded, or says why it need not be.');
