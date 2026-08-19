/**
 * The paywall must not advertise something the plan does not grant.
 *
 * On 2026-08-16 the Free card listed "3 purchase mandates". The client's
 * DEFAULT_LIMITS did say 3 — but the server had dropped free mandates to 0 on
 * 2026-07-31, because deal discovery is Pro-only and the worker skips free
 * users' mandates entirely. So the screen that takes money promised a feature
 * the buyer cannot use, and every check we had stayed green:
 *
 *   - check:billing-limits-parity compared values for pro/premium only, and
 *     only for keys the FE reads as `limits.X`. `max_mandates` was neither.
 *   - The copy is a plain string array; nothing tied it to the limits at all.
 *
 * This test closes the second hole. `check-billing-limits-parity.mjs` (widened
 * the same day) closes the first.
 *
 * The rule it encodes: every NUMBER on a plan card has to come from that plan's
 * limits, and every entitlement the plan grants should be visible on the Pro
 * card. Prose is not verifiable, so this asserts the numbers and the presence
 * of each granted feature — not the wording.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';

const REPO = path.resolve(__dirname, '../..');
const SCREEN = path.join(REPO, 'app/subscription.tsx');
const HOOK = path.join(REPO, 'src/hooks/useBillingLimits.ts');

function featureList(src: string, name: string): string[] {
  const m = new RegExp(`const ${name} = \\[(.*?)\\];`, 's').exec(src);
  if (!m) throw new Error(`${name} not found in app/subscription.tsx`);
  return [...m[1].matchAll(/'([^']+)'/g)].map((x) => x[1]);
}

function limitsBlock(src: string, marker: string): Record<string, string> {
  const at = src.indexOf(marker);
  if (at === -1) throw new Error(`${marker} not found in useBillingLimits.ts`);
  const open = src.indexOf('{', at);
  let depth = 0;
  let end = open;
  for (let i = open; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') {
      depth--;
      if (depth === 0) { end = i; break; }
    }
  }
  const body = src.slice(open, end);
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/^\s*([a-z_]+):\s*([^,\n]+),/gm)) out[m[1]] = m[2].trim();
  return out;
}

const screenSrc = readFileSync(SCREEN, 'utf8');
const hookSrc = readFileSync(HOOK, 'utf8');

const free = limitsBlock(hookSrc, 'const DEFAULT_LIMITS');
// FORCED_LIMITS nests { pro: {...}, premium: {...} }, so the block must be
// scoped to `pro:` — parsing the outer object lets premium's values (50
// mandates) silently overwrite pro's (10), which is a wrong test rather than a
// wrong screen.
const pro = limitsBlock(hookSrc.slice(hookSrc.indexOf('const FORCED_LIMITS')), 'pro:');
const freeCard = featureList(screenSrc, 'FREE_FEATURES');
const proCard = featureList(screenSrc, 'PRO_FEATURES');

describe('subscription plan cards match the limits they sell', () => {
  it('the Free card never promises mandates when free gets none', () => {
    const mandates = Number(free.max_mandates);
    const mentionsMandates = freeCard.some((f) => /mandate|deal search/i.test(f));
    if (mandates === 0) {
      expect(mentionsMandates).toBe(false);
    } else {
      expect(freeCard.some((f) => f.includes(String(mandates)))).toBe(true);
    }
  });

  it('the Pro card states the real mandate count', () => {
    expect(proCard.some((f) => f.includes(String(Number(pro.max_mandates))))).toBe(true);
  });

  it('every numeric cap named on the Free card matches DEFAULT_LIMITS', () => {
    const caps: Array<[RegExp, string]> = [
      [/watchlist/i, 'max_watchlist_items'],
      [/deal alert/i, 'max_daily_deal_alerts'],
    ];
    for (const [pattern, key] of caps) {
      const line = freeCard.find((f) => pattern.test(f));
      if (!line) continue;
      const value = free[key];
      if (value === undefined || value === 'null') continue;
      expect(line).toContain(String(Number(value)));
    }
  });

  it('every entitlement Pro grants appears on the Pro card', () => {
    // Boolean features that are false on free and true on pro are, by
    // definition, what the customer is paying for. If one is missing from the
    // card we are under-selling — which is how "unlimited watchlist" and
    // "unlimited deal alerts" went unmentioned until 2026-08-16.
    const wording: Record<string, RegExp> = {
      deal_discovery: /deal discovery/i,
      dossier_pdf: /dossier/i,
      condition_grading: /condition grading/i,
      set_completion: /set completion/i,
      advanced_analytics: /analytics/i,
    };
    const missing = Object.entries(wording)
      .filter(([key]) => free[key] === 'false' && pro[key] === 'true')
      .filter(([, re]) => !proCard.some((f) => re.test(f)))
      .map(([key]) => key);
    expect(missing).toEqual([]);
  });

  it('unlimited caps on Pro are described as unlimited, not as a number', () => {
    for (const key of ['max_watchlist_items', 'max_daily_deal_alerts']) {
      if (pro[key] !== 'null') continue;
      const claim = proCard.find((f) =>
        key === 'max_watchlist_items' ? /watchlist/i.test(f) : /deal alert/i.test(f));
      expect(claim).toBeDefined();
      expect(claim).toMatch(/unlimited/i);
    }
  });

  it('the set-completion claim names its scope', () => {
    // Measured on prod 2026-08-19: set_name coverage is 0.0% — zero rows — in
    // all 50 non-TCG categories, and their catalogue is entirely `source='seed'`.
    // An unqualified "Set completion tracker" therefore sells a Pro feature
    // that cannot work for a whiskey, watch or LEGO collector. If coverage
    // genuinely widens, widen the wording — do not delete the qualifier.
    const claim = proCard.find((f) => /set completion/i.test(f));
    expect(claim).toBeDefined();
    expect(claim).toMatch(/trading[- ]card|tcg/i);
  });

  it('the Pro card promises nothing the app does not implement', () => {
    // "Priority support" sat here until 2026-08-16 with nothing behind it. A
    // written promise to a paying user is a requirement, not copy.
    expect(proCard.some((f) => /priority support|24\/7|dedicated/i.test(f))).toBe(false);
  });
});
