#!/usr/bin/env node
/**
 * Every column the admin dashboard names in a Supabase query must exist.
 *
 * WHY (2026-09-27 walk): the Intelligence tab selected `posted_at` from
 * ugc_tiktok_metrics — the column is `snapshot_at` — and ignored the error, so
 * 6 real rows rendered as "Waiting for data". PostgREST answers an unknown
 * column with an error, not an empty list, but a caller that only looks at
 * `data` cannot tell the two apart.
 *
 * Checks, per `.from("<table>")` chain: the plain column names in
 * `.select("...")` (embeds like `creators(name)` are checked against their own
 * table), and the first argument of .eq/.neq/.gt/.gte/.lt/.lte/.like/.ilike/
 * .is/.in/.order/.contains — against scripts/schema.lock.json (the repo's
 * frozen copy of the live schema, regenerated 2026-09-27).
 *
 *   node collectai-admin/scripts/check-admin-columns.mjs   # exit 1 on a miss
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const ADMIN = join(HERE, "..");
const LOCK = JSON.parse(readFileSync(join(ADMIN, "..", "scripts", "schema.lock.json"), "utf8"));
const TABLES = LOCK.tables;

function walk(dir, out = []) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (n === "node_modules" || n.startsWith(".")) continue;
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(ts|tsx)$/.test(n)) out.push(p);
  }
  return out;
}

/** Split a select list at top-level commas. */
function splitTop(s) {
  const out = []; let depth = 0, cur = "";
  for (const ch of s) {
    if (ch === "(") depth++;
    if (ch === ")") depth--;
    if (ch === "," && depth === 0) { out.push(cur); cur = ""; } else cur += ch;
  }
  if (cur.trim()) out.push(cur);
  return out.map((x) => x.trim()).filter(Boolean);
}

/** [table, column] pairs named by one select string on `table`. */
function selectColumns(table, sel) {
  const pairs = [];
  for (let item of splitTop(sel)) {
    item = item.replace(/^[a-z_]+:/i, ""); // alias:
    const embed = item.match(/^([a-z_]+)(?:![a-z_]+)?\((.*)\)$/is);
    if (embed) { pairs.push(...selectColumns(embed[1], embed[2])); continue; }
    if (item === "*" || item.includes("(")) continue;
    const col = item.split("::")[0].split("->")[0].trim();
    if (/^[a-z_][a-z0-9_]*$/i.test(col)) pairs.push([table, col]);
  }
  return pairs;
}

// Tables the dashboard reads knowing they may not exist: each call site
// handles 42P01 by showing "not provisioned" zeros (kpi.ts), which is honest.
// Listed with the reason, so a NEW missing table still fails.
const KNOWN_UNPROVISIONED = new Map([
  ["kpi_events", "kit-funnel events from the admin template; kpi.ts:470 shows 'not provisioned'"],
  ["orders", "physical-kit orders from the admin template; kpi.ts shows 'not provisioned'"],
]);

const problems = [];
let checked = 0;
for (const file of walk(join(ADMIN, "src"))) {
  const src = readFileSync(file, "utf8");
  const re = /\.from\(\s*["'`]([a-z_]+)["'`]\s*\)/g;
  let m;
  while ((m = re.exec(src))) {
    const table = m[1];
    // The chain: from here to the next statement end or next .from(.
    let end = src.indexOf(";", m.index);
    const nextFrom = src.indexOf(".from(", m.index + 5);
    if (nextFrom !== -1 && (end === -1 || nextFrom < end)) end = nextFrom;
    const chain = src.slice(m.index, end === -1 ? undefined : end);
    const line = src.slice(0, m.index).split("\n").length;
    const where = `${relative(join(ADMIN, ".."), file)}:${line}`;
    if (!TABLES[table]) {
      if (!KNOWN_UNPROVISIONED.has(table)) problems.push(`${where}  table "${table}" does not exist`);
      continue;
    }
    const pairs = [];
    for (const s of chain.matchAll(/\.select\(\s*["'`]([^"'`]*)["'`]/g)) pairs.push(...selectColumns(table, s[1]));
    for (const f of chain.matchAll(/\.(eq|neq|gt|gte|lt|lte|like|ilike|is|in|order|contains)\(\s*["'`]([a-z_][a-z0-9_]*)["'`]/gi)) pairs.push([table, f[2]]);
    for (const [t, c] of pairs) {
      checked++;
      if (!TABLES[t]) problems.push(`${where}  embedded table "${t}" does not exist`);
      else if (!TABLES[t].includes(c)) problems.push(`${where}  ${t}.${c} does not exist`);
    }
  }
}

if (problems.length) {
  console.error(`admin column check: ${problems.length} problem(s) in ${checked} column references`);
  for (const p of problems) console.error("  " + p);
  process.exit(1);
}
console.log(`admin column check: PASS — ${checked} column references, all exist`);
