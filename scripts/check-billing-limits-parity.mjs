#!/usr/bin/env node
/**
 * Gate: the FE and BE must agree about billing limits.
 *
 * Why this exists
 * ---------------
 * `items.limits` is a split-brain contract. The front end keeps its own table
 * (FORCED_LIMITS in src/hooks/useBillingLimits.ts) and uses it whenever
 * RevenueCat resolves the plan, which is the normal iOS path. The backend keeps
 * PLAN_LIMITS in server/app/routes/billing_router.py and serves it from
 * /billing/status, which the FE falls back to when RevenueCat is unconfigured
 * (no EXPO_PUBLIC_REVENUECAT_IOS_KEY) or reports free.
 *
 * So the SAME user can be told two different things depending on which path
 * resolved first, and nothing errors either way -- a missing key reads as
 * `undefined` -> falsy -> the feature is simply locked.
 *
 * Found 2026-07-28: BE pro.advanced_analytics was False (a leftover from the
 * old three-tier model, where it was Premium-only) while FE
 * FORCED_LIMITS.pro.advanced_analytics was true. Premium is no longer
 * purchasable, so on the BE path no user could ever be granted it -- and
 * app/(tabs)/index.tsx:470 routes the Home "Extended Portfolio Insights" button
 * to the PAYWALL when that flag is false. A paying Pro subscriber was bounced
 * to an upsell for a feature they had already bought.
 *
 * What it checks
 * --------------
 * For every `limits.X` the FE actually reads in code (comments stripped -- an
 * earlier hand-audit was fooled by a stale comment referencing a key nothing
 * reads):
 *   1. X exists in the FE's DEFAULT_LIMITS and FORCED_LIMITS.{pro,premium}
 *   2. X exists in the BE's PLAN_LIMITS.{free,pro,premium}
 *   3. the FE and BE values AGREE for free, pro AND premium
 *   4. every NUMERIC cap both tables declare agrees, even when the FE never
 *      reads it as `limits.X` (that exemption is how free.max_mandates
 *      diverged 3 vs 0 unnoticed)
 *
 * Exits non-zero on any mismatch.
 */
import { readFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const FE_HOOK = path.join(REPO, 'src/hooks/useBillingLimits.ts');
const BE_ROUTER = path.join(REPO, 'server/app/routes/billing_router.py');

const fail = [];

/** Keys the FE genuinely reads, excluding comment lines. */
function feReadKeys() {
  const out = execSync(
    `grep -rhnE "limits\\??\\.[a-z_]+" ${path.join(REPO, 'src')} ${path.join(REPO, 'app')} ` +
      `--include='*.ts' --include='*.tsx' 2>/dev/null || true`,
    { encoding: 'utf8', maxBuffer: 1 << 24 },
  );
  const keys = new Set();
  for (const line of out.split('\n')) {
    // strip "NNN:" prefix, then skip comment lines (`*`, `//`)
    const body = line.replace(/^\s*\d+:/, '').trim();
    if (body.startsWith('*') || body.startsWith('//') || body.startsWith('/*')) continue;
    for (const m of body.matchAll(/limits\??\.([a-z_]+)/g)) keys.add(m[1]);
  }
  return [...keys].sort();
}

/** Parse a JS object literal body into {key: 'true'|'false'|number-ish}. */
function parseBlock(src, header) {
  const at = src.indexOf(header);
  if (at === -1) return null;
  const open = src.indexOf('{', at);
  let depth = 0, end = open;
  for (let i = open; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) { end = i; break; } }
  }
  const body = src.slice(open + 1, end);
  const obj = {};
  for (const m of body.matchAll(/^\s*([a-z_]+)\s*:\s*([^,\n]+)/gm)) {
    obj[m[1]] = m[2].trim().replace(/,$/, '');
  }
  return obj;
}

const feSrc = readFileSync(FE_HOOK, 'utf8');
const beSrc = readFileSync(BE_ROUTER, 'utf8');

const feDefault = parseBlock(feSrc, 'const DEFAULT_LIMITS');
const feForced = parseBlock(feSrc, 'const FORCED_LIMITS');
const fePro = parseBlock(feSrc.slice(feSrc.indexOf('const FORCED_LIMITS')), '  pro:');
const fePremium = parseBlock(feSrc.slice(feSrc.indexOf('const FORCED_LIMITS')), '  premium:');

// BE: PLAN_LIMITS is a python dict of dicts.
const bePlanAt = beSrc.indexOf('PLAN_LIMITS = {');
const bePlans = {};
for (const plan of ['free', 'pro', 'premium']) {
  const marker = `    "${plan}": {`;
  const at = beSrc.indexOf(marker, bePlanAt);
  if (at === -1) { fail.push(`BE PLAN_LIMITS is missing plan "${plan}"`); continue; }
  const open = beSrc.indexOf('{', at);
  const close = beSrc.indexOf('\n    },', open);
  const body = beSrc.slice(open + 1, close);
  const obj = {};
  for (const m of body.matchAll(/^\s*"([a-z_]+)"\s*:\s*([^,\n]+)/gm)) {
    obj[m[1]] = m[2].trim().replace(/,$/, '');
  }
  bePlans[plan] = obj;
}

const norm = (v) => {
  if (v === undefined) return undefined;
  const s = String(v).trim();
  if (s === 'true' || s === 'True') return 'true';
  if (s === 'false' || s === 'False') return 'false';
  if (s === 'None' || s === 'null') return 'null';
  return s;
};

if (!feDefault || !feForced || !fePro || !fePremium) {
  fail.push('could not parse FE DEFAULT_LIMITS / FORCED_LIMITS — did the shape change?');
}

const readKeys = feReadKeys();
if (readKeys.length === 0) {
  fail.push('found zero `limits.X` reads in the FE — the scan is broken, not the code');
}

for (const key of readKeys) {
  if (feDefault && !(key in feDefault)) fail.push(`FE DEFAULT_LIMITS is missing "${key}" (FE reads it → undefined → feature silently locked)`);
  if (fePro && !(key in fePro)) fail.push(`FE FORCED_LIMITS.pro is missing "${key}"`);
  if (fePremium && !(key in fePremium)) fail.push(`FE FORCED_LIMITS.premium is missing "${key}"`);
  for (const plan of ['free', 'pro', 'premium']) {
    if (bePlans[plan] && !(key in bePlans[plan])) {
      fail.push(`BE PLAN_LIMITS["${plan}"] is missing "${key}" (FE reads it off /billing/status)`);
    }
  }
  for (const [plan, feObj] of [['free', feDefault], ['pro', fePro], ['premium', fePremium]]) {
    if (!feObj || !bePlans[plan]) continue;
    const fv = norm(feObj[key]);
    const bv = norm(bePlans[plan][key]);
    if (fv !== undefined && bv !== undefined && fv !== bv) {
      fail.push(`MISMATCH ${plan}.${key}: FE=${fv} BE=${bv} — the same user is told different things depending on whether RevenueCat or /billing/status resolved first`);
    }
  }
}

// EVERY numeric limit both tables declare, not only the ones the FE reads as
// `limits.X`. Added 2026-08-16 after free.max_mandates sat at FE=3 / BE=0 for
// weeks: the server dropped free mandates to 0 on 2026-07-31 (deal discovery is
// Pro-only), the client kept saying 3, and this gate could not see it — free was
// excluded from the value comparison AND max_mandates is not read as `limits.X`
// anywhere. The paywall then advertised "3 purchase mandates" to free users who
// get none.
const numericKeys = new Set();
for (const t of [feDefault, fePro, fePremium, ...Object.values(bePlans)]) {
  for (const [k, v] of Object.entries(t || {})) {
    const n = norm(v);
    if (n !== undefined && /^-?\d+(\.\d+)?$/.test(String(n))) numericKeys.add(k);
  }
}
for (const key of numericKeys) {
  if (readKeys.includes(key)) continue; // already compared above
  for (const [plan, feObj] of [['free', feDefault], ['pro', fePro], ['premium', fePremium]]) {
    if (!feObj || !bePlans[plan]) continue;
    const fv = norm(feObj[key]);
    const bv = norm(bePlans[plan][key]);
    if (fv !== undefined && bv !== undefined && fv !== bv) {
      fail.push(`MISMATCH ${plan}.${key}: FE=${fv} BE=${bv} — a numeric cap the FE shows but never reads through limits.X`);
    }
  }
}

if (fail.length) {
  console.error('\n[billing-limits-parity] FAIL\n');
  for (const f of fail) console.error('  - ' + f);
  console.error(`\nFE: ${path.relative(REPO, FE_HOOK)}\nBE: ${path.relative(REPO, BE_ROUTER)}\n`);
  process.exit(1);
}

console.log(`[billing-limits-parity] PASS — ${readKeys.length} FE-read key(s) agree across FE and BE: ${readKeys.join(', ')}`);
