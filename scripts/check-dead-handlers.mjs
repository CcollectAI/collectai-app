#!/usr/bin/env node
/**
 * Find handler functions declared in a screen and never referenced.
 *
 * Found 2026-09-05 in app/(auth)/login.tsx: `handleMagicLink` is fully
 * implemented — validates the email, calls supabase.auth.signInWithOtp, toasts
 * on success and failure — and NOTHING calls it. `magicLinkRow` is styled and
 * never rendered. Meanwhile the file's own header comment says:
 *
 *     Login screen — email/password sign-in with magic link, Apple, and
 *     Google options.
 *
 * So the code is correct, unreachable, and advertised. The existing gates miss
 * it by construction: check-unrendered-components covers imported COMPONENTS
 * and check-unreachable-screens covers SCREENS. A dead handler inside a live
 * screen is neither.
 *
 * Heuristic and deliberately narrow: only `function handleX()` /
 * `const handleX = ` declarations, only in app/, and only when the identifier
 * appears exactly once in the file.
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = process.cwd();
const ALLOWLIST = join(ROOT, 'scripts', 'dead-handler-allowlist.txt');
const allow = new Set(
  existsSync(ALLOWLIST)
    ? readFileSync(ALLOWLIST, 'utf8').split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('#'))
    : [],
);

function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e.startsWith('.')) continue;
    const p = join(dir, e);
    statSync(p).isDirectory() ? walk(p, out) : /\.tsx?$/.test(e) && !/\.(test|spec)\./.test(e) && out.push(p);
  }
  return out;
}

const findings = [];
for (const file of walk(join(ROOT, 'app'))) {
  const raw = readFileSync(file, 'utf8');
  const rel = relative(ROOT, file);
  // Strip comments so a handler NAMED in prose does not count as a use.
  const src = raw
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
    .replace(/\/\/[^\n]*/g, (m) => ' '.repeat(m.length));

  const decls = [
    ...src.matchAll(/(?:async\s+)?function\s+(handle[A-Z][A-Za-z0-9_]*)\s*\(/g),
    ...src.matchAll(/const\s+(handle[A-Z][A-Za-z0-9_]*)\s*=/g),
  ];
  for (const d of decls) {
    const name = d[1];
    const uses = src.match(new RegExp(`\\b${name}\\b`, 'g'))?.length ?? 0;
    if (uses > 1) continue; // declared + referenced at least once
    const key = `${rel}:${name}`;
    if (allow.has(key)) continue;
    findings.push({ rel, name, line: src.slice(0, d.index).split('\n').length });
  }
}

if (!findings.length) {
  console.log('DEAD-HANDLER AUDIT: every handle* function in app/ is referenced.');
  process.exit(0);
}
console.log(`DEAD-HANDLER AUDIT: ${findings.length} unreferenced handler(s)\n`);
for (const f of findings) console.log(`  ${f.rel}:${f.line}  ${f.name}() — declared, never called`);
console.log('\nWire it up, delete it, or allowlist it in scripts/dead-handler-allowlist.txt with a reason.');
process.exit(1);
