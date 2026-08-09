#!/usr/bin/env node
/**
 * Fail when a screen pushes a route param the target route never reads.
 *
 * expo-router accepts any params object. A key the destination does not read is
 * simply dropped: no type error, no runtime warning, no log. The user watches a
 * form open blank and retypes what they already gave the app — which is exactly
 * how it was reported (2026-08-09, "this is double work and not useful").
 *
 * Three live instances existed when this check was written:
 *
 *   app/sell/pick.tsx      -> /sell/new      only `itemId` travelled, so the
 *                                            composer opened with no photo, no
 *                                            name, no price, and no evidence of
 *                                            which item was picked.
 *   app/barcode-scan.tsx   -> /add-manual    the auto-save-failure fallback sent
 *                                            SEVEN `prefill*` params; add-manual
 *                                            reads `name`/`category`/`attrs`.
 *                                            The same file's primary button used
 *                                            the right names — one handoff fixed,
 *                                            its twin left behind
 *                                            (learning_duplicate_impl_silently_drops_the_fix).
 *   app/(tabs)/index.tsx   -> /(tabs)/wishlist   `highlightId`, and wishlist.tsx
 *                                            calls useLocalSearchParams zero times.
 *
 * WHY IT COMPARES DECLARED PARAMS, NOT SUBSTRINGS
 *
 * The first version asked "does this param name appear anywhere in the target
 * file?". That passed `mode: 'watchlist'` because the word "mode" occurs in an
 * unrelated line — a false negative on a genuinely dead param, in the same
 * check meant to catch it. So the target's vocabulary is parsed from what it
 * actually reads: the `useLocalSearchParams<{...}>()` type argument plus the
 * keys it destructures out of the call.
 *
 * Usage: node scripts/check-route-param-handoff.mjs   (npm run check:params)
 */
import { readdirSync, statSync, readFileSync, existsSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = process.cwd();

/**
 * Push sites we deliberately do not police, each with the reason. An entry here
 * is a decision on record, not a silenced failure.
 */
const ALLOWLIST = [
  {
    file: 'app/import-url.tsx',
    reason:
      'Screen is deliberately unreachable and its SSRF guard blocks every host '
      + '(project_url_import_deferred). Its params are dead because the whole '
      + 'flow is dead by design; renaming them would imply it is live.',
  },
];

const files = [];
for (const root of ['app', 'src']) {
  (function walk(dir) {
    for (const e of readdirSync(dir)) {
      if (e === 'node_modules' || e.startsWith('.')) continue;
      const f = join(dir, e);
      if (statSync(f).isDirectory()) walk(f);
      else if (/\.tsx?$/.test(e)) files.push(f);
    }
  })(join(ROOT, root));
}

/** Resolve an expo-router pathname to a file, tolerating groups and index routes. */
function resolveRoute(pathname) {
  const clean = pathname.replace(/^\//, '').replace(/\?.*$/, '');
  if (clean.includes('[')) return null;            // dynamic segment: params are the segment
  const bare = clean.replace(/\(\w+\)\//g, '');
  for (const cand of [
    `app/${clean}.tsx`, `app/${clean}/index.tsx`,
    `app/${bare}.tsx`, `app/${bare}/index.tsx`,
    `app/(tabs)/${bare}.tsx`,
  ]) {
    if (existsSync(join(ROOT, cand))) return cand;
  }
  return null;
}

/**
 * The param names a route actually reads: the type argument of
 * useLocalSearchParams<{...}>() plus the keys destructured from its result.
 * Returns null when the route reads params in a way this cannot see, so the
 * caller can skip rather than guess (no false positives from a spread).
 */
function declaredParams(src) {
  if (!/useLocalSearchParams|useGlobalSearchParams/.test(src)) return new Set();
  const names = new Set();
  let sawUnparseable = false;

  for (const m of src.matchAll(/use(?:Local|Global)SearchParams\s*<\s*\{([\s\S]*?)\}\s*>/g)) {
    for (const k of m[1].matchAll(/(\w+)\s*\??\s*:/g)) names.add(k[1]);
  }
  // `const { a, b: c } = useLocalSearchParams(...)`
  for (const m of src.matchAll(/\{([^{}]*)\}\s*=\s*use(?:Local|Global)SearchParams/g)) {
    if (m[1].includes('...')) sawUnparseable = true;
    for (const part of m[1].split(',')) {
      const key = part.split(':')[0].trim();
      if (/^\w+$/.test(key)) names.add(key);
    }
  }
  // `const params = useLocalSearchParams(); params.foo`
  for (const m of src.matchAll(/(?:const|let)\s+(\w+)\s*=\s*use(?:Local|Global)SearchParams/g)) {
    const v = m[1];
    for (const u of src.matchAll(new RegExp(`\\b${v}\\.(\\w+)`, 'g'))) names.add(u[1]);
    for (const u of src.matchAll(new RegExp(`\\b${v}\\[['"](\\w+)['"]\\]`, 'g'))) names.add(u[1]);
  }
  return sawUnparseable ? null : names;
}

/**
 * The keys that actually MERGE into a params object literal.
 *
 * Two shapes both count, and one must not:
 *
 *   name: x                          -> `name`      (top level)
 *   ...(cond ? { name: x } : {})     -> `name`      (conditional spread; the
 *                                                    dominant idiom in this app)
 *   attrs: JSON.stringify({ b: c })  -> `attrs` ONLY, never `b`
 *
 * The last one is why a flat regex is not enough: it reported `barcode` as an
 * unread param at app/barcode-scan.tsx:308, where `barcode` is a key of the
 * object being SERIALISED into the (correctly named) `attrs` param. A false
 * positive in a gate is how the gate gets switched off, so the rule is: collect
 * a key only when nothing in its enclosing chain is a CALL's parentheses —
 * `(` directly preceded by an identifier character.
 */
function paramKeys(body) {
  const keys = new Set();
  const stack = [];            // { excluded: boolean }
  const excludedNow = () => stack.some((s) => s.excluded);

  for (let i = 0; i < body.length; i++) {
    const c = body[i];
    if (c === '(' || c === '[' || c === '{') {
      const prev = body.slice(0, i).replace(/\s+$/, '').slice(-1);
      const isCall = c === '(' && /[\w$)\]]/.test(prev);
      stack.push({ excluded: isCall || excludedNow() });
      continue;
    }
    if (c === ')' || c === ']' || c === '}') { stack.pop(); continue; }
    if (c === "'" || c === '"' || c === '`') {           // skip string bodies
      const q = c;
      i++;
      while (i < body.length && body[i] !== q) { if (body[i] === '\\') i++; i++; }
      continue;
    }
    if (c === ':' && !excludedNow()) {
      const before = body.slice(0, i).match(/(\w+)\s*$/);
      if (!before) continue;
      // Exclude ternary `?:` and type annotations by requiring the char before
      // the identifier to open a member list.
      const lead = body.slice(0, i - before[0].length).replace(/\s+$/, '').slice(-1);
      if (lead === '' || lead === '{' || lead === ',') keys.add(before[1]);
    }
  }
  return keys;
}

const offenders = [];
const unresolvable = [];
let checkedParams = 0;
let checkedSites = 0;
let skipped = 0;

for (const f of files) {
  const rel = relative(ROOT, f);
  if (ALLOWLIST.some((a) => a.file === rel)) continue;
  const src = readFileSync(f, 'utf8');

  // pathname: '/x' ... params: { ... }  — same object literal, in either order.
  for (const m of src.matchAll(
    /pathname:\s*['"]([^'"]+)['"][\s\S]{0,400}?params:\s*\{([\s\S]*?)\n\s*\}/g,
  )) {
    const target = resolveRoute(m[1]);
    if (!target) { skipped++; continue; }
    const declared = declaredParams(readFileSync(join(ROOT, target), 'utf8'));
    if (declared === null) { skipped++; continue; }   // spread — cannot tell
    checkedSites++;

    // A push that spreads a variable (`params: {...buildParams()}`) has keys this
    // cannot see. Counted and REPORTED rather than quietly passed: a gate that
    // silently narrows its own coverage reads as "all clear" when it is really
    // "did not look", which is the failure this whole family keeps producing.
    if (/\.\.\.[A-Za-z_$]/.test(m[2])) {
      unresolvable.push(`${rel}:${src.slice(0, m.index).split('\n').length} → ${m[1]}`);
    }
    const keys = paramKeys(m[2]);
    for (const key of keys) {
      checkedParams++;
      if (!declared.has(key)) {
        offenders.push({
          from: rel,
          to: m[1],
          target,
          key,
          line: src.slice(0, m.index).split('\n').length,
          declared: [...declared].sort().join(', ') || '(none — it never reads params)',
        });
      }
    }
  }
}

if (offenders.length) {
  console.error('\n✖ Route params pushed but never read — silently dropped:\n');
  for (const o of offenders) {
    console.error(`  ${o.from}:${o.line}  →  ${o.to}`);
    console.error(`      param '${o.key}' is not read by ${o.target}`);
    console.error(`      that route reads: ${o.declared}\n`);
  }
  console.error(`Scanned ${checkedParams} params across ${checkedSites} push sites `
    + `(${skipped} skipped: dynamic route or spread params, `
    + `${ALLOWLIST.length} allowlisted).`);
  process.exit(1);
}

if (unresolvable.length) {
  console.log(`ℹ ${unresolvable.length} push site(s) spread a variable into params, `
    + `so their keys were NOT checked:`);
  for (const u of unresolvable) console.log(`    ${u}`);
}

console.log(`✓ Every pushed route param is read by its target `
  + `(${checkedParams} params, ${checkedSites} push sites, ${skipped} skipped, `
  + `${ALLOWLIST.length} allowlisted).`);
