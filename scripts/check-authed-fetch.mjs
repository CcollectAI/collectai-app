#!/usr/bin/env node
/**
 * Gate: a request to our own API must carry a token.
 *
 * Why this exists
 * ---------------
 * Found 2026-08-19. `app/(tabs)/add.tsx` uploaded the CSV/Excel import with a
 * bare `fetch` sending only `Accept: application/json` — no Authorization —
 * while `POST /api/imports/collection` has `Depends(get_current_user_id)`.
 * Probed against prod with exactly the request the app sent:
 *
 *     HTTP 401 {"detail":"Authentication required"}
 *
 * So bulk import had NEVER inserted a row for a real user.
 *
 * THE REASON IT SURVIVED FOUR ROUNDS OF FIXES is the important part. The
 * import feature had been repaired repeatedly and each fix was real —
 * `734993b` Excel via openpyxl, `498c063` the canonical 12-column schema,
 * `43e9d8b` unpriceable imported items, `33047ee` the paired columns. Every
 * one of them is SERVER-side, downstream of a request that never arrived. And
 * `server/tests/test_import_router.py` is green at 16 tests because it calls
 * the endpoint through TestClient with `_auth_override()` — the suite injects
 * the very user the client fails to send. Both halves were tested; the seam
 * between them was not. Same shape as the `pct_of_portfolio` bug found the
 * same day.
 *
 * What it checks
 * --------------
 * Every `fetch(...)` / `fetchWithTimeout(...)` whose URL starts with
 * `${API_BASE}`, outside `src/api/httpClient.ts` itself, must have
 * `getAuthHeaders` within the preceding few lines — i.e. it attaches a bearer
 * — or be listed in PUBLIC_PATHS with a reason.
 *
 * It does NOT try to prove the endpoint requires auth; that lives in Python.
 * The rule is simpler and safer: talk to our API through the client that
 * handles tokens, refresh and timeouts, or say in writing why not.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname;
const ROOTS = [join(ROOT, 'src'), join(ROOT, 'app')];
const SELF = 'src/api/httpClient.ts';

/**
 * Endpoints that are genuinely public, each with the reason. A bare path is
 * not enough — say why, or the next reader assumes it was checked when it was
 * only added to quieten the gate.
 */
const PUBLIC_PATHS = new Map([
  ['/api/imports/template',
   'GET, no `Depends(get_current_user_id)` on import_router.import_template — ' +
   'it returns a static example CSV and is opened via Linking, not fetch.'],
]);

/** How far back to look for the getAuthHeaders that feeds this call. */
const WINDOW = 12;

function walk(dir, out = []) {
  let entries;
  try { entries = readdirSync(dir); } catch { return out; }
  for (const e of entries) {
    if (e === 'node_modules' || e.startsWith('.')) continue;
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.tsx?$/.test(p)) out.push(p);
  }
  return out;
}

const findings = [];

for (const file of ROOTS.flatMap((d) => walk(d))) {
  const rel = relative(ROOT, file);
  if (rel === SELF || rel.includes('__tests__')) continue;

  const lines = readFileSync(file, 'utf8').split('\n');
  lines.forEach((line, i) => {
    const t = line.trim();
    if (t.startsWith('//') || t.startsWith('*') || t.startsWith('/*')) return;
    // `fetch(`${API_BASE}...` or `fetchWithTimeout(`${API_BASE}...`
    const m = line.match(/\bfetch(?:WithTimeout|WithRetry)?\(\s*`\$\{API_BASE\}([^`]*)`/);
    if (!m) return;

    const path = m[1];
    const publicMatch = [...PUBLIC_PATHS.keys()].find((p) => path.startsWith(p));
    if (publicMatch) return;

    // The auth headers are built just above the call and spread into it.
    const before = lines.slice(Math.max(0, i - WINDOW), i + 1).join('\n');
    if (/getAuthHeaders\s*\(/.test(before)) return;

    findings.push({ at: `${rel}:${i + 1}`, path: path || '(dynamic)', line: t });
  });
}

if (findings.length === 0) {
  console.log('[authed-fetch] PASS — every direct call to our API attaches a bearer ' +
              `(or is one of ${PUBLIC_PATHS.size} documented public path(s)).`);
  process.exit(0);
}

console.error('[authed-fetch] FAIL — a request to our own API sends no token\n');
for (const f of findings) {
  console.error(`  ${f.at}`);
  console.error(`    path  ${f.path}`);
  console.error(`    line  ${f.line}\n`);
}
console.error(
  'Use the client in src/api/httpClient.ts — `get`/`post`/`postMultipart` attach\n' +
  'the bearer, retry through the single-flight refresh on a cold-start 401, and\n' +
  'apply a timeout. If the endpoint really is public, add it to PUBLIC_PATHS in\n' +
  'this script WITH A REASON.');
process.exit(1);
