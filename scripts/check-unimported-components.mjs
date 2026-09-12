#!/usr/bin/env node
/**
 * A component that nothing imports by name.
 *
 * check:reachable asks whether a SCREEN has an inbound navigation edge. It
 * cannot see a component, because a component is not a route. CLAUDE.md records
 * that gap as open: "a component exported from a barrel and rendered by no
 * screen is not a route, so nothing in the route graph sees it."
 *
 * A barrel re-export is NOT a use. `export { X } from './X'` keeps X compiling,
 * linted and type-checked while no screen renders it — which is how
 * WatchlistWidget and CategoryLeaderboardSection survived, and how
 * BuildProjectsSection (plural) sat next to the live BuildProjectSection
 * (singular) with nothing importing it.
 *
 * A file is reported when NO other file imports any symbol it exports, either
 * directly or through a barrel whose importer names that symbol.
 *
 * Advisory (exit 0) like check:reachable: it reports a real backlog, and a
 * blocking gate would wedge every deploy until that backlog is zero.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, dirname, normalize } from 'node:path';

const ROOTS = ['src/components'];
const SCAN = ['src', 'app'];

function walk(dir, out = []) {
  let entries;
  try { entries = readdirSync(dir); } catch { return out; }
  for (const name of entries) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) { if (name !== 'node_modules') walk(p, out); }
    else if (/\.(tsx|ts)$/.test(name) && !/\.(test|spec)\./.test(name)) out.push(p);
  }
  return out;
}

const all = SCAN.flatMap((r) => walk(r));
const fileset = new Set(all);

/**
 * A barrel is a file whose ENTIRE job is re-exporting. `app/(tabs)/index.tsx`
 * is named index.tsx and is the home SCREEN — treating it as a barrel discards
 * the single most important importer in the app and reports half of src/
 * components/home as dead. Judge by content, never by filename.
 */
const isBarrel = (f) => {
  if (!/\/index\.tsx?$/.test(f)) return false;
  const body = readFileSync(f, 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
    .trim();
  if (!body) return false;
  return body
    .split('\n')
    .filter((l) => l.trim())
    .every((l) => /^\s*(export|import)\b/.test(l));
};

function resolve(spec, from) {
  let base;
  if (spec.startsWith('@/')) base = 'src/' + spec.slice(2);
  else if (spec.startsWith('.')) base = normalize(join(dirname(from), spec));
  else return null;
  for (const ext of ['.tsx', '.ts', '/index.tsx', '/index.ts']) {
    if (fileset.has(base + ext)) return base + ext;
  }
  return null;
}

// symbol -> set of files that import that symbol from somewhere
const importedNames = new Map();
// file -> set of module paths imported (any form)
const importedPaths = new Map();

for (const f of all) {
  const src = readFileSync(f, 'utf8');
  for (const m of src.matchAll(/import\s+([^;]*?)\s+from\s+['"]([^'"]+)['"]/g)) {
    const clause = m[1];
    const target = resolve(m[2], f);
    if (target) {
      if (!importedPaths.has(target)) importedPaths.set(target, new Set());
      importedPaths.get(target).add(f);
    }
    for (const nm of clause.matchAll(/[A-Za-z_$][\w$]*/g)) {
      if (!importedNames.has(nm[0])) importedNames.set(nm[0], new Set());
      importedNames.get(nm[0]).add(f);
    }
  }
}

const dead = [];
for (const f of all) {
  if (!ROOTS.some((r) => f.startsWith(r))) continue;
  if (isBarrel(f)) continue;                           // barrels judged by their members
  const src = readFileSync(f, 'utf8');

  const exports = new Set();
  for (const m of src.matchAll(/export\s+(?:default\s+)?(?:const|function|class)\s+([A-Za-z_$][\w$]*)/g)) exports.add(m[1]);
  for (const m of src.matchAll(/export\s*\{([^}]*)\}/g)) {
    for (const part of m[1].split(',')) {
      const nm = part.trim().split(/\s+as\s+/).pop().trim();
      if (nm) exports.add(nm);
    }
  }
  // `export default X` / `export default React.memo(function X`
  for (const m of src.matchAll(/export\s+default\s+(?:React\.memo\()?(?:function\s+)?([A-Za-z_$][\w$]*)/g)) exports.add(m[1]);
  if (exports.size === 0) continue;                    // nothing to be dead

  // Imported directly by another file?
  const direct = [...(importedPaths.get(f) ?? [])].filter((imp) => !isBarrel(imp));
  if (direct.length > 0) continue;

  // Imported by NAME anywhere (covers barrel consumers that name the symbol)?
  const namedElsewhere = [...exports].some((sym) =>
    [...(importedNames.get(sym) ?? [])].some((imp) => imp !== f && !isBarrel(imp)),
  );
  if (namedElsewhere) continue;

  const viaBarrel = [...(importedPaths.get(f) ?? [])].filter((imp) => isBarrel(imp));
  dead.push({ file: f, exports: [...exports], viaBarrel });
}

if (dead.length === 0) {
  console.log('✓ no unimported components.');
  process.exit(0);
}

console.log('⚠ components nothing imports by name — they compile, lint and type-check, and no screen renders them:\n');
for (const d of dead.sort((a, b) => a.file.localeCompare(b.file))) {
  console.log(`  ${d.file}`);
  console.log(`      exports: ${d.exports.join(', ')}`);
  console.log(`      ${d.viaBarrel.length ? `re-exported by ${d.viaBarrel.join(', ')} — a barrel re-export is not a use` : 'not even re-exported'}`);
}
console.log(`\n${dead.length} component(s). Delete them, or wire them up.`);
console.log('Advisory run — this does not fail the build.');
