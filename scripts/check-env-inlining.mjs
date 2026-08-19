#!/usr/bin/env node
/**
 * Gate: every EXPO_PUBLIC_* read must be a bare `process.env.EXPO_PUBLIC_X`
 * member expression.
 *
 * WHY (2026-08-15): `useBillingLimits.ts` read the beta-unlock flag as
 *
 *     (typeof process !== 'undefined' && (process as {...}).env?.EXPO_PUBLIC_BETA_UNLOCK_ALL) || ''
 *
 * Expo's babel plugin replaces only the exact `process.env.EXPO_PUBLIC_X`
 * shape with a string literal at build time. A guarded or optional-chained
 * read does not match, so it compiled to a real runtime lookup on
 * `process.env` — which is empty in a release bundle. The flag read '' in
 * every built app: beta unlock never turned on and paid features stayed
 * gated on TestFlight, with nothing failing loudly.
 *
 * The tell is visible in the shipped binary: an inlined var's NAME disappears
 * from the bundle (only its value remains), while a runtime lookup leaves the
 * name behind in the Hermes string table.
 *
 *   unzip -p builds/<app>.ipa 'Payload/*​/main.jsbundle' | strings | grep EXPO_PUBLIC_
 *
 * Anything that prints there is being read at runtime and is therefore
 * undefined on device.
 *
 * Names appearing inside a string/template literal (log and error messages)
 * are not reads and are ignored.
 */
import { readFileSync } from 'node:fs';
import { execSync } from 'node:child_process';

const ROOTS = ['src', 'app', 'components', 'lib'];
const VAR = /EXPO_PUBLIC_[A-Z0-9_]+/g;
const INLINABLE = /process\.env\.EXPO_PUBLIC_[A-Z0-9_]+/g;

let files = [];
try {
  files = execSync(
    `grep -rl EXPO_PUBLIC_ ${ROOTS.join(' ')} --include=*.ts --include=*.tsx 2>/dev/null || true`,
    { encoding: 'utf8' },
  )
    .split('\n')
    .filter(Boolean);
} catch {
  files = [];
}

const violations = [];

for (const file of files) {
  const lines = readFileSync(file, 'utf8').split('\n');
  lines.forEach((line, idx) => {
    if (!line.includes('EXPO_PUBLIC_')) return;
    const trimmed = line.trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('*')) return;

    // Spans covered by a legal, inlinable read.
    const ok = [...line.matchAll(INLINABLE)].map((m) => [m.index, m.index + m[0].length]);
    // Spans inside a quoted string or template literal — message text, not a read.
    const strings = [...line.matchAll(/'[^']*'|"[^"]*"|`[^`]*`/g)].map((m) => [
      m.index,
      m.index + m[0].length,
    ]);

    for (const m of line.matchAll(VAR)) {
      const at = m.index;
      if (ok.some(([s, e]) => at >= s && at < e)) continue;
      if (strings.some(([s, e]) => at >= s && at < e)) continue;
      violations.push({ file, line: idx + 1, name: m[0], src: trimmed.slice(0, 120) });
    }
  });
}

if (violations.length > 0) {
  console.error(
    `\n✖ ${violations.length} EXPO_PUBLIC_ read(s) that Expo will NOT inline ` +
      `— these are undefined at runtime in a release build:\n`,
  );
  for (const v of violations) {
    console.error(`  ${v.file}:${v.line}  ${v.name}`);
    console.error(`     ${v.src}`);
  }
  console.error(
    `\n  Fix: read it as a bare member expression, e.g.\n` +
      `     const flag = (process.env.EXPO_PUBLIC_MY_FLAG || '').toLowerCase() === 'true';\n` +
      `  No 'typeof process' guard, no optional chaining, no process.env[key].\n`,
  );
  process.exit(1);
}

console.log(`✓ env inlining: ${files.length} file(s) scanned, all EXPO_PUBLIC_ reads are inlinable`);
