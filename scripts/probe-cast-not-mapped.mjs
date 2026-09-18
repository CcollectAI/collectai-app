/**
 * Class U probe: a provider that CASTS a snake_case payload to a camelCase type.
 *
 * Found twice in dealsProvider on 2026-09-18 — sales (would have rendered NaN)
 * and fee schedules (quoted 5% on a marketplace that takes 0%). TypeScript
 * cannot see it: `unwrap<T>()` and `as T` assert the shape instead of checking.
 *
 * Heuristic: a function that returns a type whose declaration contains
 * camelCase fields, from a `collectorsApi.get/post` call, WITHOUT a `.map(`
 * between the call and the return.
 */
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname);
const DIRS = ['src/data/providers', 'src/api'];

// Which exported types have camelCase fields? (from src/data/types.ts)
const typesSrc = readFileSync(path.join(ROOT, 'src/data/types.ts'), 'utf8');
const camelTypes = new Set();
for (const m of typesSrc.matchAll(/export type (\w+) = \{([\s\S]*?)\n\};/g)) {
  const [, name, body] = m;
  if (/^\s+[a-z]+[A-Z]\w*\??:/m.test(body)) camelTypes.add(name);
}

const findings = [];
for (const dir of DIRS) {
  let files = [];
  try { files = readdirSync(path.join(ROOT, dir)).filter((f) => f.endsWith('.ts')); } catch { continue; }
  for (const f of files) {
    const src = readFileSync(path.join(ROOT, dir, f), 'utf8');
    const lines = src.split('\n');
    lines.forEach((line, i) => {
      // unwrap<Type>(...) or `as Type[]` on an api call, with no map nearby
      // Skip COMMENT lines. The first run of this probe reported its own
      // write-up of the bug — the self-match in
      // learning_four_ways_a_new_gate_is_wrong.
      const code = line.trim();
      if (code.startsWith('*') || code.startsWith('//') || code.startsWith('/*')) return;
      const m = line.match(/unwrap<(\w+)>|as\s+(\w+)\[\]/);
      if (!m) return;
      const type = m[1] || m[2];
      if (!camelTypes.has(type)) return;
      const window = lines.slice(Math.max(0, i - 6), i + 8).join('\n');
      if (window.includes('.map(')) return;   // it maps — fine
      findings.push(`${dir}/${f}:${i + 1}  ${type}  —  ${line.trim().slice(0, 70)}`);
    });
  }
}
for (const f of findings) console.log(f);
console.log(`\n${findings.length} cast(s) of a snake_case payload to a camelCase type (of ${camelTypes.size} camelCase types)`);
