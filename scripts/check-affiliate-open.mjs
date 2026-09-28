#!/usr/bin/env node
/**
 * A shop link must be opened through `openAffiliateUrl`, never a bare
 * `Linking.openURL` / `WebBrowser.openBrowserAsync`.
 *
 * openAffiliateUrl is the one place that records the tap into
 * `demand_signals` (signal_type='affiliate_click') — the only data on which
 * marketplaces a buy tap goes to, and the number an affiliate network's report
 * is reconciled against. Fixed for the wishlist on 2026-08-04; on 2026-09-28
 * five more screens and the push tap still opened shop links bare, and prod
 * held 6 clicks in total, the last on 2026-08-17.
 *
 * Rule: in any app/src file that handles a shop link (mentions affiliate_url,
 * affiliateUrl, affiliateLink, listing_url or listingUrl), every open call
 * must be openAffiliateUrl, or carry a reason on its own line or the line
 * above:  // affiliate-open-ok: <why>   or   /* affiliate-open-ok: <why> *\/
 *
 *   node scripts/check-affiliate-open.mjs      # exit 1 on a violation
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname;
const SKIP = new Set(['node_modules', '__tests__', '__mocks__', '.git', 'ios', 'android']);
const HELPER = 'src/utils/affiliateHelpers.ts';
function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    if (SKIP.has(e)) continue;
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(ts|tsx)$/.test(e) && !/\.test\.tsx?$/.test(e)) out.push(p);
  }
  return out;
}
// Blank comments (keeping line numbers) so a comment NAMING the bad call is not a hit.
const blank = (s) => s
  .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
  .replace(/(^|[^:'"`])\/\/[^\n]*/g, (m, pre) => pre + ' '.repeat(m.length - pre.length));

const SHOP_LINK = /\b(affiliate_url|affiliateUrl|affiliateLink|listing_url|listingUrl)\b/;
const OPEN = /\b(Linking\.openURL|WebBrowser\.openBrowserAsync)\s*\(/g;
const REASON = /affiliate-open-ok:\s*\S/;

const failures = [];
let files = 0;
for (const file of [...walk(join(ROOT, 'app')), ...walk(join(ROOT, 'src'))]) {
  const rel = relative(ROOT, file);
  if (rel === HELPER) continue;
  const raw = readFileSync(file, 'utf8');
  const src = blank(raw);
  if (!SHOP_LINK.test(src)) continue;
  files++;
  const rawLines = raw.split('\n');
  let m;
  while ((m = OPEN.exec(src)) !== null) {
    const line = src.slice(0, m.index).split('\n').length;
    const near = (rawLines[line - 2] ?? '') + '\n' + rawLines[line - 1];
    if (REASON.test(near)) continue;
    failures.push(`${rel}:${line}  ${m[1]} opens a shop link without recording the click — use openAffiliateUrl`);
  }
}

if (failures.length) {
  console.error(`check-affiliate-open: ${failures.length} violation(s)\n  ` + failures.join('\n  '));
  process.exit(1);
}
console.log(`check-affiliate-open: OK (${files} files handle shop links)`);
