#!/usr/bin/env node
/**
 * Fails when a screen under `app/` has NO inbound navigation edge.
 *
 * `check-dead-nav.mjs` asks the opposite question — "does every push RESOLVE to
 * a file?" — and a screen can pass it forever while being impossible to arrive
 * at. That is not hypothetical: the Market hub's three signal modules were
 * unreachable for a day because the only entry point pushed `?q=` and the hub
 * hid those modules behind `!query`, and `app/import-url.tsx` has never had an
 * inbound edge at all. Both resolve fine. Neither can be reached.
 *
 * WHAT COUNTS AS AN EDGE. The hub was reached by the OBJECT form —
 * `router.push({ pathname: "/market-hub", params: … })` — which
 * check-dead-nav's string-literal regex does not see. This gate matches:
 *
 *   router.push/replace/navigate("/x")      string form
 *   router.push({ pathname: "/x" })         object form
 *   <Link href="/x"> / href={{ pathname }}  Link + Redirect
 *   pathname: "/x"                          bare (Href objects built inline)
 *
 * WHAT IS REACHABLE WITHOUT AN EDGE. Tab screens are reached by tapping the tab
 * bar, not by a push, so `app/(tabs)/*` are roots — EXCEPT one declared
 * `href: null` in the tab layout, which hides it from the bar and makes it
 * exactly as unreachable as any other orphan.
 *
 * The allowlist is for routes that are genuinely entered from outside the push
 * graph — deep links, OAuth returns, native modals. Every entry needs a reason,
 * because "add it to the allowlist" is how this class comes back.
 */
import { readdirSync, statSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const APP = join(ROOT, 'app');

const stripGroups = (s) => s.replace(/\/?\(\w+\)/g, '');
const toParam = (s) => s.replace(/\[[^\]]+\]/g, 'X');

function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e.startsWith('.')) continue;
    const f = join(dir, e);
    if (statSync(f).isDirectory()) walk(f, out);
    else if (/\.(ts|tsx)$/.test(e)) out.push(f);
  }
  return out;
}

// Entered from outside the in-app push graph. Reason required — "add it to the
// allowlist" with no reason is how this class comes back.
const ALLOWLIST = new Map([
  ['/', 'root redirect — the app entry point itself'],
  ['/+not-found', 'expo-router renders this for any unmatched URL'],
  ['/auth/callback', 'OAuth/magic-link return target, entered from the browser'],
  ['/import-url', 'iOS/Android share-sheet target; URL import is deliberately not wired into the UI'],
  ['/l/X', 'universal link. `_publish_supply_hook` writes https://sparrowcollect.com/l/<uuid> into market_hits.url, so this is entered from a shared link, never from inside the app'],
  ['/alerts', 'retired 2026-08-08, kept as a redirect so old push-notification deep links still land somewhere'],
  ['/home/portfolio', 'legacy route kept as a Redirect into the Portfolio tab'],
]);

const routes = new Map(); // normalised url -> repo-relative file
for (const f of walk(APP)) {
  const base = relative(APP, f);
  if (/(^|\/)_layout\.tsx?$/.test(base)) continue;      // layouts are not screens
  if (/(^|\/)_/.test(base)) continue;                    // _private conventions
  let r = '/' + base.replace(/\.(tsx|ts)$/, '');
  r = r.replace(/\/index$/, '');
  r = stripGroups(r) || '/';
  routes.set(toParam(r), relative(ROOT, f));
}

// --- collect inbound edges -------------------------------------------------
//
// ANY route-shaped string literal in live code counts, not just one sitting
// directly inside `router.push(`. Matching only the call form produced a false
// positive on the very first run: `app/(tabs)/wishlist.tsx` reaches /purchase
// via `router.push(limits.deal_discovery ? '/purchase' : '/subscription')`, and
// a ternary puts the literal out of reach of a call-shaped regex. Route arrays,
// config maps and `as Href` casts break it the same way.
//
// A check that cries wolf is a check that stops being read (docs/WATCHDOG.md
// records 24 days of that), so this errs toward believing an edge exists. The
// cost is a screen referenced ONLY in dead code reading as reachable; the
// benefit is that every finding it does report is real.
//
// Comments are stripped first — a route named in prose is not an edge, and
// this file's whole purpose is to notice screens nothing actually navigates to.
// Only comments that OWN their line are stripped. A `/*` inside a string
// literal would otherwise swallow every route between it and the next `*/`,
// and an over-eager stripper silently deletes the edges this gate exists to
// count — which is how the first version reported /(auth)/verify-email and
// /events/compose-announcement as orphans when both are pushed in live code.
const stripComments = (s) =>
  s
    .replace(/^\s*\/\*[\s\S]*?\*\//gm, '')
    .replace(/^\s*\*.*$/gm, '')
    .replace(/^\s*\/\/.*$/gm, '');

// Anything from the opening quote to the closing quote; the query string is
// trimmed afterwards. A character class is the wrong tool here — it stopped at
// the `?` in `` `/events/compose-announcement?eventId=${id}` `` and reported a
// live route as unreachable.
const ROUTE_LITERAL = /[`'"](\/[^`'"\s]*)[`'"]/g;

const targeted = new Set();
const sources = new Map(); // route -> Set(file)
for (const dir of ['app', 'src']) {
  for (const f of walk(join(ROOT, dir))) {
    if (f.includes('__tests__')) continue;
    const src = stripComments(readFileSync(f, 'utf8'));
    const self = relative(ROOT, f);
    for (const m of src.matchAll(ROUTE_LITERAL)) {
      const raw = m[1].split('?')[0].replace(/\/$/, '');
      const norm = toParam(stripGroups(raw).replace(/\$\{[^}]*\}/g, 'X')) || '/';
      // A screen linking to ITSELF is not an inbound edge.
      const target = routes.get(norm);
      if (target && target === self) continue;
      targeted.add(norm);
      if (!sources.has(norm)) sources.set(norm, new Set());
      sources.get(norm).add(self);
    }
  }
}

// --- tab screens are roots, unless hidden with href: null ------------------
const tabLayout = join(APP, '(tabs)', '_layout.tsx');
let hiddenTabs = new Set();
try {
  const src = readFileSync(tabLayout, 'utf8');
  // name="x" ... href: null  (within the same <Tabs.Screen> block)
  for (const m of src.matchAll(/name=\{?["'`]([\w[\]./-]+)["'`][\s\S]{0,400}?href:\s*null/g)) {
    hiddenTabs.add(m[1]);
  }
} catch {
  console.error('check-unreachable-screens: no (tabs)/_layout.tsx — cannot classify tab roots');
  process.exit(2);
}

const isTabRoot = (file) => {
  const m = file.match(/^app\/\(tabs\)\/([\w[\]./-]+)\.tsx?$/);
  if (!m) return false;
  const name = m[1].replace(/\/index$/, '');
  return !hiddenTabs.has(name);
};

// --- report ----------------------------------------------------------------
const orphans = [];
for (const [route, file] of routes) {
  if (ALLOWLIST.has(route)) continue;
  if (isTabRoot(file)) continue;
  if (targeted.has(route)) continue;
  orphans.push({ route, file });
}

// Advisory by default, like `audit_orphan_tables.py` and
// `audit_column_drift.py`: it reports a BACKLOG, and a blocking gate would
// wedge every deploy until that backlog is zero. Flip `--strict` on (and add it
// to verify:prebuild) once the list is empty — the same instruction those two
// audits carry in docs/WATCHDOG.md.
const STRICT = process.argv.includes('--strict');

if (orphans.length) {
  const say = STRICT ? console.error : console.log;
  say(`\n${STRICT ? '✗' : '⚠'} unreachable screens — no push, Link or Redirect targets them:\n`);
  for (const o of orphans) {
    say(`  ${o.route}`);
    say(`      ${o.file}`);
  }
  say(
    `\n${orphans.length} screen(s) that exist, compile, and cannot be reached.\n` +
    'Either wire an entry point, delete the screen, or add it to ALLOWLIST in\n' +
    'scripts/check-unreachable-screens.mjs WITH the reason it is entered from\n' +
    'outside the app (deep link, OAuth return, share sheet).\n' +
    (STRICT ? '' : 'Advisory run — pass --strict to fail on these.\n'),
  );
  process.exit(STRICT ? 1 : 0);
}

console.log(
  `✓ every screen is reachable — ${routes.size} route(s), ` +
  `${hiddenTabs.size} hidden tab(s), ${ALLOWLIST.size} allowlisted.`,
);
