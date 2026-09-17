/**
 * Class T probe: a field the server returns that nothing in the app reads.
 *
 * `AlertFeedItem.read` was this — the server had always sent it, the mapping
 * dropped it, and `useAlertsFeed` hardcoded `isRead: false`, so marking an
 * alert read was invisible. Enumerate the same shape everywhere.
 *
 * Run: `node scripts/probe-dropped-fields.mjs`. NOT a gate — see
 * docs/CLASS_SWEEPS.md class T for why (74 findings, most of them expected).
 *
 * Method: every field declared inside a response type literal in src/api/*.ts,
 * then grep the rest of src/ + app/ for that identifier. Zero hits outside the
 * api file = the server sends it and nobody looks.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { execSync } from 'node:child_process';
import path from 'node:path';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname);
const API_DIR = path.join(ROOT, 'src/api');

const files = readdirSync(API_DIR).filter((f) => f.endsWith('.ts'));
const rows = [];

for (const f of files) {
  const src = readFileSync(path.join(API_DIR, f), 'utf8');
  const lines = src.split('\n');
  // Fields look like `  name: type;` or `      name?: type;` inside a get<{...}>
  // or an exported type. Comments and code lines are skipped by requiring the
  // line to be only `ident?: something;`.
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^\s{2,}([a-z_][A-Za-z0-9_]*)\??:\s*[^=]+;\s*$/);
    if (!m) continue;
    const field = m[1];
    if (field.length < 3) continue;
    rows.push({ file: f, line: i + 1, field });
  }
}

// One grep per distinct field name, outside src/api.
const byField = new Map();
for (const r of rows) {
  if (!byField.has(r.field)) byField.set(r.field, []);
  byField.get(r.field).push(r);
}

const dropped = [];
for (const [field, sites] of byField) {
  let hits = '';
  try {
    hits = execSync(
      `grep -rIl --include='*.ts' --include='*.tsx' -e '\\b${field}\\b' src app 2>/dev/null | grep -v '^src/api/' || true`,
      { cwd: ROOT, encoding: 'utf8' },
    ).trim();
  } catch { hits = ''; }
  if (!hits) dropped.push({ field, sites });
}

dropped.sort((a, b) => a.field.localeCompare(b.field));
for (const d of dropped) {
  console.log(`${d.field}  —  ${d.sites.map((s) => `${s.file}:${s.line}`).join(', ')}`);
}
console.log(`\n${dropped.length} field(s) declared in src/api and referenced nowhere else (of ${byField.size} distinct)`);
