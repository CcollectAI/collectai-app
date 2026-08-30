#!/usr/bin/env node
/**
 * Fail when the Pro card sells something the app does not ship.
 *
 * WHY THIS EXISTS (2026-08-30)
 *
 * `app/subscription.tsx` listed **'Condition grading'** as a Pro benefit for
 * roughly four months after the feature was SHELVED (2026-05-02).
 * `GradingSection` sat imported-but-never-rendered in `app/item/[id].tsx`, so a
 * subscriber paying EUR 4.99/mo had nothing to tap. Nothing caught it:
 *
 *  - `subscriptionPlanCards.test.ts` checks NUMERIC caps and mandate counts.
 *    A non-numeric bullet like "Condition grading" is invisible to it.
 *  - `check:unrendered` should have flagged the dead import and did not: a
 *    type-only import from '@/components/GradingSection' left that path string
 *    in the body, so the value import looked used. Fixed the same day.
 *  - The limit flag `condition_grading` is still `true` for pro on BOTH sides,
 *    so every parity gate agreed with itself. FE and BE can be in perfect
 *    agreement about a feature that no longer renders.
 *
 * That is the gap this closes: agreement between two config files is not
 * evidence that a screen exists.
 *
 * THE RULE
 *
 * 1. Every bullet in PRO_FEATURES must have an entry in CLAIMS below. An
 *    undeclared bullet FAILS — you cannot add a selling point without saying
 *    what backs it. This is deliberate: it is the enumerate-mechanically rule,
 *    not a judgment call about which bullets look risky.
 * 2. A claim's `limit` must be a real key in useBillingLimits' DEFAULT_LIMITS.
 * 3. A claim's `renders` (when given) must actually appear as `<Component` in
 *    the app tree. This is the half that catches shelving.
 * 4. Nothing in SHELVED may be advertised at all.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join } from 'node:path';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SCREEN = join(ROOT, 'app/subscription.tsx');
const HOOK = join(ROOT, 'src/hooks/useBillingLimits.ts');

/** bullet substring -> what backs it. `renders: null` = enforced by a limit only. */
const CLAIMS = [
  { match: /purchase mandates/i,  limit: 'max_mandates',          renders: null },
  { match: /watchlist/i,          limit: 'max_watchlist_items',   renders: null },
  { match: /target hit/i,         limit: 'max_daily_deal_alerts', renders: null },
  { match: /deal discovery/i,     limit: 'deal_discovery',        renders: null },
  { match: /set completion/i,     limit: 'set_completion',        renders: null },
  { match: /advanced analytics/i, limit: 'advanced_analytics',    renders: 'MarketplacePricesSection' },
  { match: /no ads/i,             limit: 'show_ads',              renders: null },
];

/** Features whose FE is shelved. Advertising one of these is the bug. */
const SHELVED = [
  { name: 'Condition grading',  match: /condition grading/i, since: '2026-05-02' },
  { name: 'Dossier PDF export', match: /dossier/i,           since: '2026-08-30' },
  { name: 'Price trend chart',  match: /price trend/i,       since: '2026-05-02' },
];

const SKIP_DIRS = new Set(['node_modules', '.git', '__tests__', '__mocks__', 'ios', 'android']);
function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    if (SKIP_DIRS.has(e)) continue;
    const full = join(dir, e);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (full.endsWith('.tsx')) out.push(full);
  }
  return out;
}
const stripComments = (s) =>
  s.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^[ \t]*\/\/.*$/gm, ' ');

const screenSrc = stripComments(readFileSync(SCREEN, 'utf8'));
const hookSrc = readFileSync(HOOK, 'utf8');

const block = screenSrc.match(/const PRO_FEATURES\s*=\s*\[([\s\S]*?)\];/);
if (!block) {
  console.error('[paywall-claims] FAIL — could not find PRO_FEATURES in app/subscription.tsx');
  process.exit(1);
}
const bullets = [...block[1].matchAll(/'([^']+)'/g)].map((m) => m[1]);
if (bullets.length === 0) {
  console.error('[paywall-claims] FAIL — PRO_FEATURES parsed as EMPTY. Refusing to pass: an\n' +
                '  empty parse is indistinguishable from a clean card, which is the exact\n' +
                '  failure mode this gate exists to catch.');
  process.exit(1);
}

const limitKeys = new Set(
  [...(hookSrc.match(/const DEFAULT_LIMITS[\s\S]*?\};/) || [''])[0]
    .matchAll(/^\s*([a-z_]+):/gm)].map((m) => m[1]),
);

const failures = [];
const rendered = walk(join(ROOT, 'app')).concat(walk(join(ROOT, 'src')))
  .map((f) => stripComments(readFileSync(f, 'utf8'))).join('\n');

for (const b of bullets) {
  const shelved = SHELVED.find((s) => s.match.test(b));
  if (shelved) {
    failures.push(`Pro card sells "${b}", but ${shelved.name} has been SHELVED since ${shelved.since}.\n` +
      `      A paying member has nothing to tap. Remove the bullet and the\n` +
      `      MONETIZATION.md row, or un-shelve the feature.`);
    continue;
  }
  const claim = CLAIMS.find((c) => c.match.test(b));
  if (!claim) {
    failures.push(`Pro card sells "${b}" and no CLAIMS entry declares what backs it.\n` +
      `      Add one in scripts/check-paywall-claims.mjs naming its limit key and,\n` +
      `      if it has a screen, the component that renders it.`);
    continue;
  }
  if (!limitKeys.has(claim.limit)) {
    failures.push(`"${b}" claims limit \`${claim.limit}\`, which is not in DEFAULT_LIMITS.`);
  }
  if (claim.renders && !new RegExp(`<${claim.renders}\\b`).test(rendered)) {
    failures.push(`"${b}" is backed by <${claim.renders}>, which is never rendered anywhere.\n` +
      `      The bullet outlived its screen — the Condition-grading failure exactly.`);
  }
}

if (failures.length) {
  console.error('[paywall-claims] FAIL\n');
  for (const f of failures) console.error('  - ' + f + '\n');
  console.error(`${failures.length} paywall claim(s) the app does not back.`);
  process.exit(1);
}
console.log(`[paywall-claims] PASS — all ${bullets.length} Pro bullets are backed by a limit and a screen.`);
