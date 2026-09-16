#!/usr/bin/env node
/**
 * A view granted to `authenticated` must filter by the caller.
 *
 * WHY: a Postgres view runs as its OWNER unless `security_invoker = true`, so
 * RLS on the base tables does NOT apply to rows read through it. A view over
 * per-member tables therefore needs one of:
 *
 *   - `security_invoker = true` (RLS on the base tables applies), or
 *   - `auth.uid()` in its own body (it filters itself, in either mode).
 *
 * The house pattern is the second — `v_item_values_v1` carries
 * `WHERE i.user_id = auth.uid()` with a comment saying exactly why.
 *
 * WHAT THIS CAUGHT (2026-09-17, class sweep J): the repo's
 * `20260430_fix_chat_inbox_view_typing.sql` DROPs and re-CREATEs
 * `v_chat_inbox_v1` with neither. **Production is not exposed** — the live view
 * was verified to end in `WHERE p.user_id = auth.uid()`, and both chat tables
 * have member-scoped RLS SELECT policies — but the repo file and the database
 * had drifted apart, so replaying that migration would have DROPPED the filter
 * and handed every member every DM thread, `last_message_body` included.
 *
 * A DROP + CREATE is the dangerous shape: a fresh view takes default
 * reloptions, so any earlier blanket `ALTER VIEW … security_invoker = true`
 * (there are three, all 20260424) is silently undone.
 *
 * `server/scripts/audit_rls_coverage.py` cannot see this: it scans
 * `relkind IN ('r','p')` — tables only.
 *
 * Exempt a view that genuinely holds nothing per-member (a catalogue, a
 * vocabulary) with a reason on the line above the CREATE:
 *     -- rls-ok: catalogue prices, identical for every member
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const DIR = join(ROOT, 'supabase', 'migrations');

/** Strip `--` and block comments. Without this the scanner read the SENTENCE
 *  "CREATE OR REPLACE VIEW requires the column list" in a comment and reported
 *  a view named `requires` (2026-09-17). Grep-matches-its-own-prose, from the
 *  checker's side. */
const stripSql = (sql) => sql
  // keep the newlines inside a block comment, so line numbers still line up
  .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
  .replace(/--[^\n]*/g, '');

/** Views the CLIENT reads directly. A view no client queries cannot hand a
 *  member another member's row, whatever its reloptions — and scoping to these
 *  is what takes this gate from 23 historical findings to the live surface. */
function clientReadNames() {
  const out = new Set();
  const walk = (dir) => {
    for (const e of readdirSync(dir)) {
      if (e === 'node_modules' || e === '__tests__' || e.startsWith('.')) continue;
      const p = join(dir, e);
      if (statSync(p).isDirectory()) walk(p);
      else if (/\.(ts|tsx)$/.test(e)) {
        const src = readFileSync(p, 'utf8');
        for (const m of src.matchAll(/\.from\(\s*['"]([a-z0-9_]+)['"]/gi)) out.add(m[1].toLowerCase());
      }
    }
  };
  for (const d of ['src', 'app']) {
    try { walk(join(ROOT, d)); } catch { /* directory may not exist */ }
  }
  return out;
}

/** The contiguous run of `--` comment lines directly above line `lineNo` (1-based). */
function commentBlockAbove(lines, lineNo) {
  const out = [];
  for (let i = lineNo - 2; i >= 0; i--) {
    const t = lines[i].trim();
    if (t === '') { if (out.length) break; continue; }
    if (!t.startsWith('--')) break;
    out.unshift(t);
  }
  return out.join('\n');
}

/** Statement-level scan: each CREATE [OR REPLACE] VIEW up to its terminating ';'. */
const CREATE_VIEW = /create\s+(?:or\s+replace\s+)?view\s+(?:if\s+not\s+exists\s+)?([\w."]+)/gi;

const files = readdirSync(DIR).filter((f) => f.endsWith('.sql')).sort();
const CLIENT_READS = clientReadNames();

// ── Which tables are per-member? Any CREATE TABLE whose body has a user_id. ──
// Mechanical rather than a hand-written list, so a new per-member table is
// covered the day it lands instead of when someone remembers to add it here.
const PER_MEMBER = new Set();
for (const file of files) {
  const sql = stripSql(readFileSync(join(DIR, file), 'utf8'));
  for (const m of sql.matchAll(/create\s+table\s+(?:if\s+not\s+exists\s+)?([\w."]+)([\s\S]*?);\s*(?:\n|$)/gi)) {
    if (/\buser_id\b|\bdm_user_a\b|\bowner_id\b/i.test(m[2])) {
      PER_MEMBER.add(m[1].replace(/"/g, '').replace(/^public\./, '').toLowerCase());
    }
  }
}

// ── Migrations are a LOG: only each view's LAST definition is the live one. ──
// Flagging every historical CREATE produced 65 findings, most of them already
// superseded — a checker that cries wolf stops being read.
const latest = new Map();
let scanned = 0;

for (const file of files) {
  const raw = readFileSync(join(DIR, file), 'utf8');
  const sql = stripSql(raw);
  // The BUG shape, in this file's own history: `near` was taken from the
  // stripped text, where every comment is gone — so the `-- rls-ok:` marker the
  // error message tells you to write could never match. Find the statement in
  // the stripped SQL, read the reason from the RAW lines. stripSql preserves
  // newlines, so the line numbers agree.
  const lines = raw.split('\n');
  for (const m of sql.matchAll(CREATE_VIEW)) {
    scanned++;
    const name = m[1].replace(/"/g, '').replace(/^public\./, '');
    const rest = sql.slice(m.index);
    const end = rest.search(/;\s*(?:\n|$)/);
    const body = end === -1 ? rest : rest.slice(0, end);
    const lineNo = sql.slice(0, m.index).split('\n').length;
    latest.set(name, {
      at: `supabase/migrations/${file}:${lineNo}`,
      name,
      body,
      // The whole comment block immediately above, not a fixed window: a reason
      // worth reading runs to several lines, and a 4-line lookback silently
      // ignored one written 8 lines up — the marker the error message asks for,
      // present and not counted. Resolve per BLOCK, not per line.
      near: commentBlockAbove(lines, lineNo),
      dropped: /drop\s+view/i.test(sql.slice(Math.max(0, m.index - 200), m.index)),
      // does a later ALTER in the same file turn invoker on for this view?
      altered: new RegExp(`alter\\s+view\\s+(?:public\\.)?"?${name}"?[\\s\\S]{0,120}security_invoker\\s*=\\s*true`, 'i').test(sql.slice(m.index)),
    });
  }
}

const findings = [];
for (const v of latest.values()) {
  if (/auth\.uid\s*\(\s*\)/i.test(v.body)) continue;
  if (/security_invoker\s*=\s*true/i.test(v.body) || v.altered) continue;
  if (/rls-ok:/i.test(v.near)) continue;
  // Only views that actually touch per-member data can leak it.
  const reads = [...PER_MEMBER].filter((t) => new RegExp(`\\b${t}\\b`, 'i').test(v.body));
  // A COLUMN check as well as a table check, and this is not belt-and-braces:
  // the table list is built from CREATE TABLE in this repo, and the chat tables
  // were created in the dashboard, so `v_chat_inbox_v1` — the view this gate
  // exists for — was invisible to the table rule. A gate that misses its own
  // worked example is asserting the shape of a fix while the effect is broken.
  const ownerColumn = /\b(user_id|dm_user_a|dm_user_b|owner_id)\b/i.test(v.body);
  if (!reads.length && !ownerColumn) continue;
  if (!CLIENT_READS.has(v.name.toLowerCase())) continue;
  findings.push({ ...v, reads: reads.length ? reads.slice(0, 3) : ['a per-member column'] });
}

if (findings.length) {
  console.error(`✗ view RLS — ${findings.length} view(s) neither filter by auth.uid() nor set security_invoker:`);
  for (const f of findings) {
    console.error(`   ${f.at}  ${f.name}  reads ${f.reads.join(", ")}${f.dropped ? "  (DROP + CREATE — resets reloptions)" : ""}`);
  }
  console.error('\n   A view runs as its OWNER by default, so RLS on the base tables does not');
  console.error('   apply. Add "WHERE <owner column> = auth.uid()" to the body (the pattern in');
  console.error('   v_item_values_v1), set security_invoker = true, or add');
  console.error('   "-- rls-ok: <why this view holds nothing per-member>" above the CREATE.');
  process.exit(1);
}
console.log(`✓ view RLS — ${scanned} view definition(s), each filtered, invoker-scoped, or explained.`);
