#!/usr/bin/env node
/**
 * A write that bypasses CachedDataProvider must invalidate what it changed.
 *
 * WHY (2026-09-24): add-manual inserts into `items` with supabase-js directly,
 * so the cached collection (`items:list`, TTL 5 min) was never cleared. A seller
 * who had just added a card opened Sell and read "Nothing in your collection
 * yet". Two more direct `items` writes (catalog refresh, item detail patch) had
 * the same gap. The provider's own mutations invalidate; these went around it.
 *
 * Flags `.from('<cached table>')` followed within 4 lines by insert / update /
 * delete / upsert, OUTSIDE src/data/ (providers are wrapped by the cache class),
 * unless an invalidation call appears within the next 80 lines, or the line (or
 * the one above the `.from`) carries `// cache-ok: <reason>`.
 *
 * Usage: node scripts/check-cache-bypass.mjs   (npm run check:cache-bypass)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
// Tables whose reads are cached in src/data/CachedDataProvider.ts, and the call
// that invalidates each.
const CACHED = {
  items: /invalidateItemCaches\(/,
  watchlist_items: /cacheClear\(|invalidateWatchlist/,
};
const walk = (dir, out = []) => {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e === '__tests__' || e.startsWith('.')) continue;
    const f = join(dir, e);
    if (statSync(f).isDirectory()) walk(f, out);
    else if (/\.(ts|tsx)$/.test(e)) out.push(f);
  }
  return out;
};

const findings = [];
let scanned = 0;
for (const abs of ['app', 'src'].flatMap((d) => walk(join(ROOT, d)))) {
  const rel = relative(ROOT, abs);
  if (rel.startsWith('src/data/')) continue;
  const lines = readFileSync(abs, 'utf8').split('\n');
  scanned += 1;
  lines.forEach((line, i) => {
    const m = line.match(/\.from\(\s*['"]([a-z_]+)['"]\s*\)/);
    if (!m || !(m[1] in CACHED)) return;
    if (/^\s*(\/\/|\*)/.test(line)) return;
    const win = lines.slice(i, i + 4).join(' ');
    if (!/\.(insert|update|delete|upsert)\(/.test(win)) return;
    if (/cache-ok:\s*\S/.test(line) || /cache-ok:\s*\S/.test(lines[i - 1] ?? '')) return;
    const after = lines.slice(i, i + 80).join('\n');
    if (CACHED[m[1]].test(after)) return;
    findings.push(`${rel}:${i + 1}  direct write to \`${m[1]}\` with no cache invalidation after it`);
  });
}

if (scanned === 0) {
  console.error('check:cache-bypass scanned no files — the scan is broken.');
  process.exit(1);
}
if (findings.length) {
  console.error(`✗ cache bypass — ${findings.length} direct write(s) leave a cached view stale:`);
  for (const f of findings) console.error(`   ${f}`);
  console.error('\n   Call invalidateItemCaches() (src/data/CachedDataProvider.ts) after the write,');
  console.error('   or add "// cache-ok: <why nothing cached can go stale>".');
  process.exit(1);
}
console.log(`✓ cache bypass — every direct write to a cached table invalidates (${scanned} files).`);
