#!/usr/bin/env node
/**
 * Fail when a screen IMPORTS a component and never puts it in the tree.
 *
 * Found on 2026-08-20, reported as "the send button on marketplace does not
 * work". `app/listings.tsx` imported `ShareToChatSheet`, held a `shareFor`
 * state, computed a `sharePayload` memo and rendered a paper-plane on every
 * tile — and the element itself was never in the returned JSX. Tapping share
 * set the state, the memo recomputed, and nothing opened. The whole feature
 * was one line short, on the screen it was written for.
 *
 * WHY NOTHING CAUGHT IT
 *
 * - `tsc` is happy: an unused binding is legal TypeScript.
 * - `eslint` DID say it — `'ShareToChatSheet' is defined but never used` —
 *   as a WARNING, in a repo carrying dozens of them, and `verify:prebuild`
 *   does not run lint at all. A signal nothing blocks on is not a gate.
 * - `check:reachable` asks whether a SCREEN has an inbound route edge. A
 *   component mounted by JSX has no route, so that gate passes forever.
 * - `check-dead-nav` asks whether a route target exists. There is no route.
 *
 * This is its own AXIS, and it is the [[learning_silent_fallbacks_hide_dead_features]]
 * shape at component scale: writer and reader both present, never connected,
 * and the disconnection renders as nothing rather than as an error.
 *
 * THE RULE
 *
 * A PascalCase value imported from a `components/` module must appear
 * somewhere in the file besides its own import statement. Deliberately narrow:
 *   - `import type` / `type X` specifiers are skipped (a type is not a tree).
 *   - Only `components/` paths, so hooks, tokens and helpers are none of its
 *     business — eslint already reports those, and this gate blocks.
 *   - Any other reference counts, not just `<X`. A component passed as a prop
 *     (`ListEmptyComponent={Empty}`) or aliased is legitimately rendered.
 */
import { readFileSync } from 'node:fs';
import { readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join, relative } from 'node:path';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const ROOTS = ['app', 'src'];
const SKIP_DIRS = new Set(['node_modules', '.git', '__tests__', '__mocks__', 'ios', 'android']);

function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (full.endsWith('.tsx')) out.push(full);
  }
  return out;
}

/**
 * Comments out, both directions — this gate was WRONG in both on the day it
 * was written, and each error was the mirror of the other:
 *
 *  - a component mentioned only in a `//` comment ("moved to
 *    CategorySpecificSection") counted as USED, hiding a stale import;
 *  - a commented-out `// import { SellTimingBadge } ...`, kept deliberately
 *    beside the note explaining how to restore it, counted as an IMPORT and
 *    was reported as unrendered.
 *
 * Stripping first makes both go away: a comment is neither a reference nor a
 * declaration.
 */
function stripComments(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, ' ')  // /* ... */ and JSX {/* ... */}
    .replace(/^[ \t]*\/\/.*$/gm, ' ');   // whole-line // comments
}

/** All import statements, as {names, source, raw}. */
function parseImports(src) {
  const out = [];
  // Non-greedy up to `from '...'`; [\s\S] so a multi-line specifier list works.
  const re = /import\s+(type\s+)?([\s\S]*?)\s+from\s+['"]([^'"]+)['"]/g;
  let m;
  while ((m = re.exec(src)) !== null) {
    const [raw, typeOnly, clause, source] = m;
    // NOTE 2026-08-30: this used to `continue` on a type-only import, which
    // dropped it from `out` entirely — so its raw text was never stripped from
    // the body below. That was a HOLE, not a shortcut: a module PATH contains
    // the component's name, so
    //     import type { GradingLookupResult } from '@/components/GradingSection';
    // left the literal string `GradingSection` sitting in the body and made the
    // VALUE import one line above it look used. `app/item/[id].tsx` imported
    // GradingSection and never rendered it for ~4 months while this gate said
    // PASS, and the paywall sold "Condition grading" the whole time.
    // Type-only imports are still not CHECKED — a type is not a tree — but they
    // must be REMOVED from the body, which is why they are collected now.
    const names = [];
    if (typeOnly) { out.push({ names, source, raw, typeOnly: true }); continue; }
    // `import Default, { A, B as C, type D } from` — take both halves.
    const braced = clause.match(/\{([\s\S]*)\}/);
    const beforeBrace = clause.split('{')[0].replace(/,\s*$/, '').trim();
    if (beforeBrace && !beforeBrace.startsWith('*')) names.push(beforeBrace);
    if (braced) {
      for (const part of braced[1].split(',')) {
        const spec = part.trim();
        if (!spec || spec.startsWith('type ')) continue;
        // `A as B` binds B — the local name is what the JSX would use.
        names.push(spec.includes(' as ') ? spec.split(/\s+as\s+/)[1].trim() : spec);
      }
    }
    out.push({ names, source, raw, typeOnly: false });
  }
  return out;
}

const failures = [];

for (const rootDir of ROOTS) {
  for (const file of walk(join(ROOT, rootDir))) {
    const src = stripComments(readFileSync(file, 'utf8'));
    const imports = parseImports(src);
    // Everything that is NOT an import statement — the file's actual body.
    let body = src;
    for (const imp of imports) body = body.replace(imp.raw, '');

    for (const imp of imports) {
      if (imp.typeOnly) continue;   // collected only so its raw is stripped above
      if (!imp.source.includes('components/')) continue;
      for (const name of imp.names) {
        if (!/^[A-Z][A-Za-z0-9_]*$/.test(name)) continue;
        const used = new RegExp(`\\b${name}\\b`).test(body);
        if (!used) {
          failures.push(
            `${relative(ROOT, file)}: imports \`${name}\` from '${imp.source}' and never renders it.\n` +
            `      A component that is imported but never in the tree is a feature that is\n` +
            `      wired everywhere except the one place that shows it. Render it, or drop\n` +
            `      the import and the state that feeds it.`,
          );
        }
      }
    }
  }
}

if (failures.length) {
  console.error('[unrendered-components] FAIL\n');
  for (const f of failures) console.error('  - ' + f + '\n');
  console.error(`${failures.length} unrendered component import(s).`);
  process.exit(1);
}
console.log('[unrendered-components] PASS — every imported component is in a tree.');
