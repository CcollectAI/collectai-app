#!/usr/bin/env node
/**
 * Fail when App Store / Play copy claims something the app does not ship.
 *
 * WHY THIS EXISTS (2026-09-01)
 *
 * `docs/app-store-aso.md` — the copy pasted verbatim into App Store Connect —
 * carried a whole section headed "CONDITION & GRADING TRACKER", describing
 * logging grades from PSA, CGC and BGS. That feature was SHELVED on
 * 2026-05-02: `GradingSection` is orphaned and `/grading/lookup` returns
 * `cert_verified=false`. It also claimed "37 data sources" against 15 live
 * adapters, "54 categories" against 56, and named Mercari, StockX and
 * BrickLink as comparison sources when all three are in DISABLED_ADAPTERS.
 *
 * This is the same defect `check:paywall-claims` was written for — copy
 * written from intent rather than from the code — with a worse blast radius.
 * App Store Review Guideline 2.3 is specifically about metadata matching
 * actual functionality, so this is a rejection reason, not a style note.
 *
 * THE RULES
 *
 * 1. No SHELVED feature may be named. Each entry says when and why.
 * 2. Every named marketplace must be a live adapter, not one in
 *    DISABLED_ADAPTERS.
 * 3. A category count in the copy must match the shipped category count.
 * 4. A "N data sources" claim must match the live adapter count. Prefer no
 *    number at all: it drifts every time an adapter is disabled, and nobody
 *    re-reads marketing copy when they switch one off.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join } from 'node:path';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const COPY = join(ROOT, 'docs/app-store-aso.md');
const copy = readFileSync(COPY, 'utf8');

/** Features that are NOT in the app. Naming one in store copy is the bug. */
const SHELVED = [
  { re: /condition grading|grading tracker|AI-assisted condition estimation/gi,
    what: 'PSA/CGC condition grading', since: '2026-05-02',
    why: 'GradingSection is orphaned; /grading/lookup returns cert_verified=false' },
  { re: /price history over time|track price history/gi,
    what: 'the price-history chart', since: '2026-05-02',
    why: 'shelved — coverage is uneven across categories' },
  { re: /dossier/gi,
    what: 'the Valuation Report / dossier', since: '2026-08-30',
    why: 'FE shelved; the BE route stays' },
  { re: /chat with other collectors|collector chat/gi,
    what: 'collector chat', since: 'never shipped',
    why: 'no chat screen exists and it was explicitly gated' },
];

/** Marketplaces the copy may name, checked against the live adapter set. */
const MARKET_NAMES = {
  'eBay': 'ebay', 'TCGPlayer': 'tcgplayer', 'TCGplayer': 'tcgplayer',
  'Cardmarket': 'cardmarket', 'Discogs': 'discogs', 'Mercari': 'mercari_us',
  'StockX': 'stockx', 'BrickLink': 'bricklink', 'Catawiki': 'catawiki',
  'Chrono24': 'chrono24', 'Whatnot': 'whatnot', 'PriceCharting': 'pricecharting',
};

const routing = readFileSync(join(ROOT, 'server/app/agents/marketplace_routing.py'), 'utf8');
const disabledBlock = /DISABLED_ADAPTERS[^=]*=\s*\{([\s\S]*?)\n\}/.exec(routing);
const DISABLED = new Set(
  disabledBlock ? [...disabledBlock[1].matchAll(/"([a-z0-9_]+)"/g)].map((m) => m[1]) : [],
);

const cats = readFileSync(join(ROOT, 'src/constants/categories.ts'), 'utf8');
const CATEGORY_COUNT = [...cats.matchAll(/slug: '[a-z_0-9]+'/g)].length;

// An empty parse would make every rule vacuously pass — the failure this gate
// exists to catch, one level up.
if (DISABLED.size === 0 || CATEGORY_COUNT === 0) {
  console.error(`[aso-claims] FAIL — parsed ${DISABLED.size} disabled adapters and ` +
    `${CATEGORY_COUNT} categories. An empty parse makes every claim "true"; ` +
    `the source files changed shape. Fix the patterns above.`);
  process.exit(1);
}

const failures = [];
const lineOf = (idx) => copy.slice(0, idx).split('\n').length;

// 1. shelved features
for (const s of SHELVED) {
  for (const m of copy.matchAll(s.re)) {
    failures.push(`docs/app-store-aso.md:${lineOf(m.index)} names ${s.what} — SHELVED ${s.since}.\n` +
      `      ${s.why}.\n` +
      `      App Store Review 2.3: metadata must match what the app does.`);
  }
}

// 2. named marketplaces must be live
for (const [label, adapter] of Object.entries(MARKET_NAMES)) {
  if (!DISABLED.has(adapter)) continue;
  const re = new RegExp(`\\b${label}\\b`, 'g');
  for (const m of copy.matchAll(re)) {
    failures.push(`docs/app-store-aso.md:${lineOf(m.index)} names ${label} as a source, ` +
      `but "${adapter}" is in DISABLED_ADAPTERS — the app cannot query it.`);
  }
}

// 3. category counts
// PLURAL only. `/(\d{2})\s+categor/` also matched "10 category-specific
// questions", which is a claim about a FAQ page, not about how many
// categories ship — a false positive found by reading the gate's own output
// instead of trusting its count.
for (const m of copy.matchAll(/(\d{2})\s+categories\b/gi)) {
  if (Number(m[1]) !== CATEGORY_COUNT) {
    failures.push(`docs/app-store-aso.md:${lineOf(m.index)} claims ${m[1]} categories; ` +
      `src/constants/categories.ts ships ${CATEGORY_COUNT}.`);
  }
}

// 4. source counts — prefer none at all
for (const m of copy.matchAll(/(\d{2})\+?\s+(?:data|marketplace)\s+sources/gi)) {
  failures.push(`docs/app-store-aso.md:${lineOf(m.index)} claims ${m[1]} data sources. ` +
    `Only ${Object.keys(MARKET_NAMES).length - [...DISABLED].filter((d) => Object.values(MARKET_NAMES).includes(d)).length} ` +
    `of the named ones are live, and 28 adapters are disabled.\n` +
    `      Prefer NO number: it drifts every time an adapter is switched off, ` +
    `and nobody re-reads marketing copy when they do.`);
}

if (failures.length) {
  console.error('[aso-claims] FAIL\n');
  for (const f of failures) console.error('  - ' + f + '\n');
  console.error(`${failures.length} store-copy claim(s) the app does not back.`);
  process.exit(1);
}
console.log(`[aso-claims] PASS — store copy names no shelved feature, no disabled ` +
  `marketplace, and ${CATEGORY_COUNT} categories throughout.`);
