#!/usr/bin/env node
/**
 * A caught exception's `.message` is for the log, never the screen.
 *
 * WHY (2026-09-14): Analytics showed a banner reading "categories: Request
 * timed out after 15000ms". That fix enumerated screens rendering `{error}` and
 * missed the TOAST branch of the same rule — 79 on-screen sites of
 * `showToast({ message: err?.message || 'Failed to …' })`. For any backend call
 * the fallback never runs, because `ApiError.message` is always set, and it is
 * `"POST /purchase/mandates failed (409): Mandate limit reached (3)…"` — method,
 * path and status code in front of the sentence the server wrote for the member.
 *
 * Every member-facing error string goes through `userErrorMessage(err, fallback)`
 * (src/lib/userErrorMessage.ts), which keeps a written sentence and drops the
 * plumbing. This gate fails on the raw shapes:
 *
 *   err.message || 'x'          err?.message ?? 'x'
 *   (err as Error)?.message || 'x'
 *   err instanceof Error ? err.message : 'x'
 *
 * BLIND SPOT: the first shape knows the catch names err/e/error/ex/caught only
 * (a wider pattern flags chat and notification `.message` DATA fields). A
 * `catch (apiErr)` passes. All caught-variable names were enumerated 2026-09-14
 * and none other leaked.
 *
 * A line that only LOGS or PARSES the message is fine — mark it with
 * `// raw-error-ok: <why>` on the same line or the line above. Lines that call
 * logger / console / Sentry / logLoad are exempt automatically.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const ROOTS = ['app', 'src/components', 'src/hooks'];

const RAW_SHAPES = [
  // err.message || 'x'   (err as Error)?.message ?? 'x'
  /\b(?:err|e|error|ex|caught)\b(?:\s+as\s+\w+)?\)?\??\.message\s*(?:\|\||\?\?)/,
  // err instanceof Error ? err.message : 'x'
  /instanceof\s+Error\s*\?\s*\(?\s*\w+\s*\)?\??\.message\b/,
  // e instanceof Error && e.message ? ` (${e.message})` : ''
  /instanceof\s+Error\s*&&\s*\w+\.message\b/,
];

const LOG_CALL = /\b(?:logger\.\w+|console\.\w+|Sentry\b|logLoad)\s*[?.(]/;
const ALLOW = /raw-error-ok:/;

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === '__tests__' || name === 'node_modules') continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (/\.(tsx?|jsx?)$/.test(name) && !/\.test\./.test(name)) out.push(p);
  }
  return out;
}

const offenders = [];
for (const root of ROOTS) {
  for (const file of walk(root)) {
    const lines = readFileSync(file, 'utf8').split('\n');
    lines.forEach((line, i) => {
      if (!RAW_SHAPES.some((re) => re.test(line))) return;
      if (LOG_CALL.test(line)) return;
      if (ALLOW.test(line) || (i > 0 && ALLOW.test(lines[i - 1]))) return;
      offenders.push(`${file}:${i + 1}: ${line.trim()}`);
    });
  }
}

if (offenders.length) {
  console.error(
    `[raw-error-copy] FAIL — ${offenders.length} site(s) put a caught exception's text on screen.\n` +
      `Use userErrorMessage(err, fallback) from '@/lib/userErrorMessage', or mark a log/parse-only\n` +
      `line with // raw-error-ok: <why>.\n`,
  );
  for (const o of offenders) console.error('  ' + o);
  process.exit(1);
}
console.log('[raw-error-copy] PASS — no caught exception text reaches a toast, banner or alert');
