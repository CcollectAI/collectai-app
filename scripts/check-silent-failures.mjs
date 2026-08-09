#!/usr/bin/env node
/**
 * Mechanical sweep for the silent-failure classes that keep shipping.
 *
 * Every one of these has the same shape: something fails or is missing, a
 * construct degrades it to a plausible-looking value (0, [], null, "no
 * results"), and the UI renders that as fact. Nothing throws, nothing logs, so
 * it survives review, typecheck, tests and CI, and is found only when a user
 * says "this number is wrong".
 *
 * Written after 2026-07-25, when hand-triage repeatedly missed instances and
 * Merle found them instead. Judgment does not converge; a checker does.
 *
 * Usage: node scripts/check-silent-failures.mjs [--strict]
 *   default  report findings, exit 0 (informational sweep)
 *   --strict exit 1 on any finding (for verify:prebuild once at zero)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const STRICT = process.argv.includes('--strict');
const SCAN = ['app', 'src'];

function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e === '__tests__' || e.startsWith('.')) continue;
    const f = join(dir, e);
    if (statSync(f).isDirectory()) walk(f, out);
    else if (/\.(ts|tsx)$/.test(e)) out.push(f);
  }
  return out;
}
const lineOf = (s, i) => s.slice(0, i).split('\n').length;

const files = SCAN.flatMap((d) => walk(join(ROOT, d)));
const findings = [];
const add = (cls, file, line, detail) => findings.push({ cls, file, line, detail });

for (const abs of files) {
  const rel = relative(ROOT, abs);
  const src = readFileSync(abs, 'utf8');
  const isMock = /\/mocks?\//.test(rel);

  // ── A. Aggregate computed over a deliberately capped list ───────────────
  // `listItems({limit: 50})` then `.reduce((sum,x)=>sum+…)` reports the value
  // of 50 items as the whole portfolio. This shipped live on Home behind
  // FEATURE_DATA_INSIGHTS_ALERTS=true.
  for (const m of src.matchAll(/\breduce\s*\(\s*\(\s*(\w+)[^)]*\)\s*=>\s*\1\s*\+/g)) {
    const fnStart = Math.max(0, src.lastIndexOf('const', m.index) - 1200);
    const ctx = src.slice(fnStart, m.index);
    const lim = ctx.match(/limit\s*:\s*(\d+)/);
    if (lim) add('capped-aggregate', rel, lineOf(src, m.index), `sums a list fetched with limit: ${lim[1]}`);
  }

  // ── B. catch that swallows: no logger call anywhere in the block ────────
  for (const m of src.matchAll(/catch\s*(?:\([^)]*\))?\s*\{/g)) {
    let depth = 0, i = m.index + m[0].length - 1, end = -1;
    for (; i < src.length; i++) {
      if (src[i] === '{') depth++;
      else if (src[i] === '}') { depth--; if (depth === 0) { end = i; break; } }
    }
    if (end === -1) continue;
    const body = src.slice(m.index, end);
    if (body.length > 4000) continue;
    // A `best-effort:` marker means the swallow is a written decision with a
    // stated reason, not an oversight. Same principle as the auth allowlist:
    // exceptions must be justified in the file, never left to judgment.
    if (/best-effort:/.test(body)) continue;
    const logs = /logger\.|console\.|showToast|setError|throw\b|Sentry/.test(body);
    if (!logs) add('swallowed-catch', rel, lineOf(src, m.index), 'catch with no log, toast, setError or rethrow');
    else if (/logger\.(warn|info|debug)\s*\(/.test(body) && !/logger\.error/.test(body)) {
      add('prod-invisible-log', rel, lineOf(src, m.index), 'only logger.warn/info — STRIPPED in release builds');
    }
  }

  // ── C. supabase write whose result is discarded ─────────────────────────
  // Resolves rather than throws, so an unchecked write reports success.
  for (const m of src.matchAll(/(^|\n)\s*await\s+supabase\s*\.\s*from\([^)]*\)\s*\.\s*(update|insert|delete|upsert)\b/g)) {
    add('unchecked-write', rel, lineOf(src, m.index), `${m[2]}() result discarded — cannot detect failure`);
  }

  // ── C2. raw `fetch` write whose response status is never checked ─────────
  // Identical hazard, different construct: fetch RESOLVES on 4xx/5xx instead of
  // throwing, so `await fetch(...)` with no `res.ok` check inside a try/catch
  // means the catch never fires and the failure leaves no trace at all.
  //
  // Rule C only matched `supabase.from()`, so it reported 0 while four real
  // instances shipped — every one a copy of the same PUT /settings block
  // (onboarding, AppearanceSection ×2, ProfileEditSection). A Korean user's
  // region/currency/locale 500'd against the CHECK constraints for months and
  // the app showed no error, because nobody read the status. Found 2026-07-31.
  //
  // Only flags MUTATIONS: a bare GET that degrades to a default is a separate
  // (often deliberate) choice. `await fetch(...)` that is `return`ed is a
  // wrapper handing the response to its caller — not a discarded result.
  for (const m of src.matchAll(/(^|\n)([ \t]*)(return\s+)?await\s+fetch\s*\(/g)) {
    if (m[3]) continue;                                  // `return await fetch(` — caller checks
    const start = m.index + m[0].length;
    const window = src.slice(m.index, start + 500);      // the call + its options object
    if (!/method\s*:\s*['"`](PUT|POST|PATCH|DELETE)['"`]/i.test(window)) continue;  // reads are out of scope
    if (/\.(ok|status)\b/.test(window)) continue;        // status is inspected
    add('unchecked-write', rel, lineOf(src, m.index),
        'await fetch() response never checked — fetch resolves on 4xx/5xx, so the catch never fires');
  }


  // ── E. Fabricated demo/mock data reachable in production ────────────────
  // The worst silent failure: the UI renders invented numbers as the user's
  // real data. portfolioAnalyticsStore returned DEMO_SERIES (a fake
  // 1200 -> 2050 curve) and DEMO_SETS whenever the backend failed, ungated,
  // on both Home and Analytics. The sibling DEMO_ITEMS path HAD been gated --
  // the fix was applied to one of three and never swept.
  // Files under a mocks/ directory legitimately DEFINE mock data; whether the
  // mock provider is reachable in a release build is a separate question,
  // answered in src/data/index.ts (which now refuses to default to mock).
  for (const m of isMock ? [] : src.matchAll(/\b(DEMO|MOCK|SAMPLE|FAKE)_[A-Z0-9_]+\b/g)) {
    const ln = lineOf(src, m.index);
    const line = src.split('\n')[ln - 1] ?? '';
    const t = line.trim();
    if (t.startsWith('//') || t.startsWith('*') || t.startsWith('/*')) continue; // comment
    if (/^\}?,?\s*\[[^\]]*\]\s*\)?;?$/.test(t)) continue;                     // deps array
    if (/^(export\s+)?(const|let|var|type|interface)\s/.test(t)) continue;      // definition
    if (/^import\b/.test(t)) continue;
    const ctx = src.slice(Math.max(0, m.index - 200), m.index + 100);
    if (/__DEV__|isDev|MODE\s*===|process\.env\.NODE_ENV/.test(ctx)) continue;  // gated
    add('ungated-demo-data', rel, ln, `${m[0]} reachable in a release build`);
  }

  // ── D. money/value coerced to 0 inside a sum ────────────────────────────
  // "unknown price" rendered as "worth 0" and silently folded into a total.
  if (!isMock) {
    for (const m of src.matchAll(/\+\s*\(?\s*[\w.?]*\b(price|value|amount|total|worth)\b[\w.]*\s*(\?\?|\|\|)\s*0/gi)) {
      add('unknown-as-zero', rel, lineOf(src, m.index), 'unpriced item counted as 0 inside a sum');
    }
  }
}

// All six classes are at 0 and each was proven by reintroducing its bug, so
// every one now blocks. swallowed-catch and prod-invisible-log were a reported
// backlog until 2026-07-25, when they were closed mechanically: 91 catches got
// a logger.error, and 182 warn/info calls inside catch blocks were raised to
// error so a failure survives the release build that strips warn/info.
const BLOCKING = ['ungated-demo-data', 'capped-aggregate', 'unchecked-write',
                  'unknown-as-zero', 'swallowed-catch', 'prod-invisible-log'];
const byClass = findings.reduce((a, f) => ((a[f.cls] ??= []).push(f), a), {});
const ORDER = ['ungated-demo-data', 'capped-aggregate', 'unchecked-write', 'unknown-as-zero', 'swallowed-catch', 'prod-invisible-log'];
const SEVERITY = {
  'ungated-demo-data': 'renders invented data as the user\'s real data',
  'capped-aggregate': 'renders a partial number as the whole truth',
  'unchecked-write': 'reports success when the write failed',
  'unknown-as-zero': 'renders "unknown" as "zero"',
  'swallowed-catch': 'failure leaves no trace at all',
  'prod-invisible-log': 'trace exists in dev, stripped in the build that matters',
};

console.log('\n=== silent-failure sweep ===\n');
for (const cls of ORDER) {
  const list = byClass[cls] ?? [];
  console.log(`${String(list.length).padStart(4)}  ${cls.padEnd(20)} ${SEVERITY[cls]}`);
}
console.log();
for (const cls of ORDER) {
  const list = byClass[cls] ?? [];
  if (!list.length || !BLOCKING.includes(cls)) continue;
  console.log(`── ${cls} (${list.length})`);
  for (const f of list.slice(0, 40)) console.log(`   ${f.file}:${f.line}  ${f.detail}`);
  if (list.length > 40) console.log(`   … ${list.length - 40} more`);
  console.log();
}
// Blocking = a REGRESSION, not a backlog. These four are at 0 and each was
// proven to fail before being fixed, so any non-zero count is something newly
// broken. swallowed-catch (91) and prod-invisible-log (181) are a known,
// reported backlog — blocking on them would make this check permanently red,
// and a check that is always red is one nobody reads.
const blocking = BLOCKING.reduce((n, c) => n + (byClass[c]?.length ?? 0), 0);
const backlog = ORDER.filter((c) => !BLOCKING.includes(c)).reduce((n, c) => n + (byClass[c]?.length ?? 0), 0);
console.log(`total: ${findings.length} — ${blocking} blocking (regressions), ${backlog} backlog (reported, not blocking)\n`);
process.exit(STRICT && blocking > 0 ? 1 : 0);
