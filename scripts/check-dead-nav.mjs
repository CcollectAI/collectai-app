#!/usr/bin/env node
/**
 * Fails when router.push/replace/navigate targets a route with no file.
 *
 * expo-router resolves an unknown path to nothing useful: the button either
 * does nothing or lands on a blank screen. No type error, no runtime throw —
 * the same silent shape as the rest of this codebase's failure modes.
 *
 * Route groups — the `(auth)` / `(tabs)` directories — are transparent in the
 * URL, so they must be stripped from BOTH sides before comparing. Stripping
 * them from only one side is why the first version of this check reported 21
 * false positives: every `/(auth)/login` looked dead when it is perfectly valid.
 */
import { readdirSync, statSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const APP = join(ROOT, 'app');

const stripGroups = (s) => s.replace(/\/?\(\w+\)/g, '');
const toParam = (s) => s.replace(/\[[^\]]+\]/g, 'X');

function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e.startsWith('.')) continue;
    const f = join(dir, e);
    if (statSync(f).isDirectory()) walk(f, out);
    else if (/\.(ts|tsx)$/.test(e)) out.push(f);
  }
  return out;
}

// Every routable file under app/, normalised to its URL form.
const routes = new Set();
for (const f of walk(APP)) {
  let r = '/' + relative(APP, f).replace(/\.(tsx|ts)$/, '');
  r = r.replace(/\/index$/, '').replace(/\/_layout$/, '');
  r = stripGroups(r) || '/';
  routes.add(toParam(r));
}

const NAV_RE = /router\.(push|replace|navigate)\(\s*[`'"]([^`'"]+)/g;
const findings = [];

for (const dir of ['app', 'src']) {
  for (const f of walk(join(ROOT, dir))) {
    if (f.includes('__tests__')) continue;
    const src = readFileSync(f, 'utf8');
    for (const m of src.matchAll(NAV_RE)) {
      const raw = m[2].split('?')[0].replace(/\/$/, '');
      if (!raw.startsWith('/')) continue; // relative push — resolved at runtime
      const norm = stripGroups(raw).replace(/\$\{[^}]*\}/g, 'X') || '/';
      if (!routes.has(norm)) {
        findings.push({
          file: relative(ROOT, f),
          line: src.slice(0, m.index).split('\n').length,
          target: raw,
        });
      }
    }
  }
}

if (!findings.length) {
  console.log(`[dead-nav] PASS — every router target resolves (${routes.size} routes)`);
  process.exit(0);
}

console.error(`\n[dead-nav] FAIL — ${findings.length} navigation target(s) with no route file:\n`);
for (const f of findings) console.error(`  ${f.file}:${f.line}  ->  ${f.target}`);
console.error('\nAdd the route under app/, or fix the path. A push to a missing');
console.error('route fails silently — the button simply does nothing.\n');
process.exit(1);
