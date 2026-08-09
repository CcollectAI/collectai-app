#!/usr/bin/env node
/**
 * Fail on a read of `items` that counts ARCHIVED rows as if the user still
 * owned them.
 *
 * `items.archived` is a real column (boolean NOT NULL DEFAULT false) and the
 * app offers archiving as a soft-delete: `itemsProvider.archiveItem()` and the
 * Items-tab bulk action both set it. Eight VIEWS respect it —
 * `user_public_profile_v1`, `api_user_analytics_v1`, `api_user_price_card_v1/v2`,
 * `v_user_collection_profile_v1`, `v_owned_item_keys_v1`,
 * `api_category_item_status_user_v1`, `user_public_profiles`.
 *
 * Nothing that reads the TABLE directly does. So on 2026-08-09 the state was:
 * archiving an item removed it from your public profile and your analytics, and
 * left it fully present in your own collection list and your portfolio value.
 * Prod had 0 archived rows, so the feature had never once been exercised and
 * nothing looked wrong.
 *
 * It became load-bearing when P2P settlement started archiving the SELLER's item
 * on a completed trade (`_settle_completed_trade`). Without this gate the seller
 * sells a thing and still sees it in their collection, still counts its value in
 * their portfolio, and can still open it — while their public profile says it is
 * gone. The trade "completed" and the object never left.
 *
 * This is its own AXIS. No existing gate covers it:
 *   - check-constraint-drift  — asks whether a WRITTEN value is legal, not
 *                               whether a READ is scoped.
 *   - check-silent-failures   — asks whether an error is swallowed. Nothing
 *                               errors here; the row is simply included.
 *   - audit_key_overlap       — compares JOIN values. The join is fine.
 * An archived row is a VALID row. Only asking "is this read scoped to what the
 * user still owns?" finds it.
 *
 * THE RULE: any SELECT that reads `items` on behalf of one user must exclude
 * archived rows, or carry an `archived-exempt:` marker saying why not.
 *
 * Legitimate exemptions exist and must be stated, not assumed — historical
 * series that would rewrite the past by dropping rows, and admin/data-moat
 * aggregates that deliberately count everything.
 *
 * Usage: node scripts/check-archived-filter.mjs   (npm run check:archived)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = process.cwd();
const PY_ROOTS = ['server/app', 'server/workers'];
const TS_ROOTS = ['src', 'app'];

const EXEMPT_MARKER = 'archived-exempt:';

/** Reads of the items TABLE. Views are excluded — the archived-aware ones
 *  already filter, and a view is not a table read we can scope here. */
const PY_ITEMS_READ = /\b(?:FROM|JOIN)\s+(?:public\.)?items\b(?!\s*_)/i;
/** A statement that returns rows. UPDATE/INSERT/DELETE are writes: archiving
 *  itself is a write, and a write scoped to an id needs no archived predicate. */
const PY_IS_SELECT = /\bSELECT\b/i;
const PY_IS_WRITE = /^\s*(?:UPDATE|INSERT|DELETE)\b/i;

/**
 * Only SQL, not prose. `db_helpers.py`'s module docstring documents a
 * `WHERE user_id = $N` example and would otherwise be reported as a query.
 * Real SQL in this codebase starts at one of these tokens (fragments that get
 * concatenated start at WHERE/AND/FROM/JOIN).
 */
const PY_LOOKS_LIKE_SQL = /^\s*(?:--\s*)?(?:WITH|SELECT|WHERE|AND|FROM|JOIN|\()/i;

/**
 * A read that names a specific row by primary key is a PERMISSION or detail
 * lookup — "does this item exist and is it yours", "fetch the row the user just
 * tapped". The caller already named the row, so archived is not a filter it
 * should apply: you still own an archived item and must still be able to open
 * and un-archive it. Excluding these is what keeps the gate about COLLECTION
 * reads, which is the axis that actually broke.
 *
 * `(?<![_A-Za-z])` so `user_id = $1` and `item_id = $1` do NOT match — only a
 * bare `id` / `i.id`.
 */
const PY_BY_ID = /(?<![_A-Za-z])id\s*(?:=|IN)\s*(?:\$|ANY|\()/i;

/** The axis: a read that returns a SET of one user's items. */
const PY_USER_SCOPED = /user_id\s*=\s*\$|user_id\s*=\s*ANY|\buser_id\b/i;

const files = [];
function walk(dir, exts) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return;
  }
  for (const e of entries) {
    if (e === 'node_modules' || e === '__pycache__' || e === '.venv') continue;
    const p = join(dir, e);
    const st = statSync(p);
    if (st.isDirectory()) walk(p, exts);
    else if (exts.some((x) => p.endsWith(x))) files.push(p);
  }
}

/**
 * Pull string literals out of Python source, with the line each starts on.
 * SQL in this codebase lives in triple-quoted blocks (multi-line queries) and
 * plain quotes (one-liners like the value_summary COUNT). Both must be scanned:
 * the one-liner `SELECT COUNT(*) FROM items WHERE user_id = $1` was one of the
 * real offenders.
 */
function pyStringLiterals(src) {
  const out = [];
  const re = /("""|''')([\s\S]*?)\1|"([^"\n]*)"|'([^'\n]*)'/g;
  let m;
  while ((m = re.exec(src)) !== null) {
    const body = m[2] !== undefined ? m[2] : m[3] !== undefined ? m[3] : m[4];
    if (body === undefined) continue;
    const line = src.slice(0, m.index).split('\n').length;
    out.push({ body, line, end: m.index + m[0].length });
  }
  return out;
}

const findings = [];

// ---------------------------------------------------------------- Python ---
for (const r of PY_ROOTS) walk(join(ROOT, r), ['.py']);
for (const f of files) {
  const src = readFileSync(f, 'utf8');
  if (!/items/i.test(src)) continue;
  const lines = src.split('\n');
  for (const lit of pyStringLiterals(src)) {
    const sql = lit.body;
    if (!PY_ITEMS_READ.test(sql)) continue;
    if (!PY_IS_SELECT.test(sql)) continue;
    if (PY_IS_WRITE.test(sql)) continue;
    if (!PY_LOOKS_LIKE_SQL.test(sql)) continue;
    if (PY_BY_ID.test(sql)) continue;
    if (!PY_USER_SCOPED.test(sql)) continue;
    if (/archived/i.test(sql)) continue;
    // A marker may sit in the SQL itself or in the ~6 lines above the literal,
    // which is where a Python comment explaining the query lives.
    const ctxFrom = Math.max(0, lit.line - 7);
    const ctx = lines.slice(ctxFrom, lit.line + sql.split('\n').length).join('\n');
    if (ctx.includes(EXEMPT_MARKER)) continue;
    findings.push({
      file: relative(ROOT, f),
      line: lit.line,
      snippet: sql.trim().split('\n').slice(0, 2).join(' ').replace(/\s+/g, ' ').slice(0, 110),
    });
  }
}

// -------------------------------------------------------------- TypeScript ---
files.length = 0;
for (const r of TS_ROOTS) walk(join(ROOT, r), ['.ts', '.tsx']);
for (const f of files) {
  const src = readFileSync(f, 'utf8');
  if (!src.includes(".from('items')") && !src.includes('.from("items")')) continue;
  const lines = src.split('\n');
  for (let i = 0; i < lines.length; i++) {
    if (!/\.from\(['"]items['"]\)/.test(lines[i])) continue;
    // The chain: everything until the statement ends. `.select(` makes it a
    // read; `.update(`/`.delete(`/`.insert(` make it a write.
    const chain = lines.slice(i, Math.min(lines.length, i + 14)).join('\n');
    const stmt = chain.split(/;\s*$/m)[0];
    if (!/\.select\(/.test(stmt)) continue;
    if (/\.(update|delete|insert|upsert)\(/.test(stmt)) continue;
    // Same rule as PY_BY_ID: a read that names the row is a detail/permission
    // read, not a collection read. `.eq('id', …)` / `.in('id', […])`.
    if (/\.(eq|in)\(\s*['"]id['"]/.test(stmt)) continue;
    if (/archived/i.test(stmt)) continue;
    const ctx = lines.slice(Math.max(0, i - 7), i + 14).join('\n');
    if (ctx.includes(EXEMPT_MARKER)) continue;
    findings.push({
      file: relative(ROOT, f),
      line: i + 1,
      snippet: lines[i].trim().slice(0, 110),
    });
  }
}

if (findings.length === 0) {
  console.log('check-archived-filter: PASS — every items read is scoped to unarchived rows (or states why not).');
  process.exit(0);
}

console.error(`check-archived-filter: FAIL — ${findings.length} items read(s) count archived rows as owned.\n`);
for (const x of findings) {
  console.error(`  ${x.file}:${x.line}`);
  console.error(`      ${x.snippet}`);
}
console.error(`
Fix: add an archived predicate to the read —
  SQL:      AND NOT i.archived          (or  AND i.archived IS NOT TRUE)
  supabase: .eq('archived', false)
Or, if the read genuinely must count archived rows, put a comment on it:
  ${EXEMPT_MARKER} <why this read counts items the user no longer owns>
`);
process.exit(1);
