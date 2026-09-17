#!/usr/bin/env node
/**
 * Screen sweep — walk EVERY route on an Android device in one run and let a
 * machine do the checks a person kept doing by eye.
 *
 * Why (2026-09-15): walks were one deep link at a time, from memory, one state
 * per screen, with a rebuild after each finding. There was no inventory, so no
 * coverage number and no way to see convergence. This script is the inventory
 * (scripts/walk/routes.json, one entry per file under app/) plus the mechanical
 * part of a walk. A person then reviews the contact sheet only for what a
 * machine cannot judge: layout, copy, wrong numbers.
 *
 * Per route: deep link → wait until the UI dump stops changing → screenshot +
 * uiautomator XML + the app's JS error log → checks:
 *   FOCUS        another window has focus (ANR dialog, permission prompt, other app)
 *   WRONG_SCREEN the deep link never left Home (re-sent once) — the route was not judged
 *   CRASH        FATAL EXCEPTION in io.sparrowcollect.app
 *   SLOW_LOAD    a spinner/skeleton still up at --spinner-budget (default 5s)
 *   STILL_LOADING a spinner/skeleton still up at --timeout
 *   NO_TITLE     no text in the header band
 *   NO_BACK      no "Go back" control (any locale's common.go_back_a11y)
 *   NO_CLUSTER   the header bell/gear cluster is missing
 *   NO_NAVBAR    the five-tab bar is missing
 *   RAW_TEXT     plumbing on screen: "15000ms", "failed (500)", undefined, NaN,
 *                [object, an i18n key like "home.title", "{{count}}", €-10
 *   UNTRANSLATED (--locale ≠ en) a string equal to an en.json value whose
 *                translation in that locale differs
 *   NOT_IDLE     uiautomator never saw the UI idle within 10 s (continuous animation)
 *   NO_DUMP      no UI tree even with a 30 s dump — see the screenshot
 *   JS_ERRORS    count of E/ReactNativeJS lines while on the screen (info only)
 *
 * States, no Gradle build needed:
 *   --locale nl        the app's own Settings → Language (local-only), verified, restored
 *   --small            720x1520 @ 320dpi (a ~360dp phone), restored afterwards
 *   failure state      install an APK whose bundle points at a dead API
 *                      (scripts/android_jsswap.sh with EXPO_PUBLIC_API_BASE_URL
 *                      overridden) and run with --label failure
 *
 * Fixtures for dynamic routes are resolved from Supabase as the walk account
 * (items, listings, events, deals, projects, offers) when SUPABASE_URL,
 * SUPABASE_ANON_KEY, WALK_EMAIL and WALK_PASSWORD are set — `npm run walk`
 * supplies the first two via `eas env:exec production`. Anything unresolved is
 * reported as SKIPPED with the missing fixture, never silently dropped. READ
 * ONLY: the sweep never taps a control.
 *
 * Usage:
 *   node scripts/walk/sweep.mjs [--only <substr>] [--label <name>] [--locale nl]
 *        [--small] [--serial emulator-5560] [--timeout 30] [--restart-every 15]
 *        [--fixtures file.json] [--out dir]
 * Output: builds/walk/<timestamp>-<label>/index.html (contact sheet),
 *         report.json, shots/, dumps/.
 */
import { spawnSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const PKG = 'io.sparrowcollect.app';
const ADB = process.env.ADB || '/usr/local/share/android-commandlinetools/platform-tools/adb';

// ── args ─────────────────────────────────────────────────────────────────────
const argv = process.argv.slice(2);
const arg = (name, dflt) => { const i = argv.indexOf(`--${name}`); return i >= 0 ? argv[i + 1] : dflt; };
const flag = (name) => argv.includes(`--${name}`);
if (flag('help')) { console.log(readFileSync(new URL(import.meta.url)).toString().split('*/')[0]); process.exit(0); }
const SERIAL = arg('serial', 'emulator-5560');
const ONLY = arg('only', null);
const LOCALE = arg('locale', 'en');
const SMALL = flag('small');
const TIMEOUT_S = Number(arg('timeout', '30'));
const RESTART_EVERY = Number(arg('restart-every', '15'));
// A loading indicator still up this long after arriving is a finding (SLOW_LOAD).
const SPINNER_BUDGET_S = Number(arg('spinner-budget', '5'));
const SIGNED_OUT = flag('signed-out');
// LOCAL time: an ISO (UTC) stamp named a 22:00 run "2000".
const pad = (n) => String(n).padStart(2, '0');
const now = new Date();
const stamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`;
const LABEL = arg('label', [LOCALE !== 'en' ? LOCALE : '', SMALL ? 'small' : ''].filter(Boolean).join('-') || 'normal');
const OUT = arg('out', join(ROOT, 'builds', 'walk', `${stamp}-${LABEL}`));

// ── adb helpers ──────────────────────────────────────────────────────────────
const adb = (args, opts = {}) => {
  const r = spawnSync(ADB, ['-s', SERIAL, ...args], { encoding: opts.binary ? 'buffer' : 'utf8', timeout: Math.max(1000, Math.round((opts.timeout ?? 60) * 1000)), killSignal: 'SIGKILL', maxBuffer: 64 * 1024 * 1024 });
  if (r.error && !opts.allowFail) throw new Error(`adb ${args.join(' ')}: ${r.error.message}`);
  return r.stdout;
};
const sh = (cmd, opts) => adb(['shell', cmd], opts);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const focus = () => (sh('dumpsys window | grep mCurrentFocus', { allowFail: true }) || '').trim();
// One adb round-trip: dump straight to stdout instead of dump-to-file + cat.
// uiautomator itself waits for the UI to go idle, so an animating spinner or
// skeleton makes a dump slow — which is why the wait loop below dumps as few
// times as it can.
// Capped: uiautomator waits for the UI to go IDLE, and a spinning screen can
// hold one dump for 30 s — one catalogue-item route took 102 s on 2026-09-15.
// A capped-out dump returns '' and the wait loop treats it as still loading.
const DUMP_CAP_S = 10;
const dumpXml = (capS = DUMP_CAP_S) => {
  const out = adb(['exec-out', 'uiautomator dump /dev/tty'], { allowFail: true, timeout: Math.max(2, capS) }) || '';
  const a = out.indexOf('<?xml'); const b = out.lastIndexOf('</hierarchy>');
  return a >= 0 && b > a ? out.slice(a, b + '</hierarchy>'.length) : '';
};
const parseNodes = (xml) => [...xml.matchAll(/<node [^>]*>/g)].map((m) => {
  const n = m[0];
  const get = (k) => (n.match(new RegExp(` ${k}="([^"]*)"`)) || [])[1] ?? '';
  const b = get('bounds').match(/\[(\d+),(\d+)\]\[(\d+),(\d+)\]/);
  const [x1, y1, x2, y2] = b ? b.slice(1).map(Number) : [0, 0, 0, 0];
  const unesc = (s) => s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
  return { text: unesc(get('text')), desc: unesc(get('content-desc')), cls: get('class'), pkg: get('package'), x1, y1, x2, y2 };
});
// ActivityIndicator renders a ProgressBar; our Skeleton carries accessibilityLabel="Loading" (Skeleton.tsx).
// A bare "Loading…" text counts too (listing detail renders one — the first
// sweep read it as a settled screen).
const isLoadingText = (t) => /^(Loading|Laden|Wird geladen|Chargement|Cargando|読み込み中|로딩 중|불러오는 중)[.…]*$/i.test(t.trim());
const isLoading = (nodes) => nodes.some((n) => n.pkg === PKG && (/ProgressBar/.test(n.cls) || n.desc === 'Loading' || (n.text && isLoadingText(n.text))));
const signature = (nodes) => nodes.filter((n) => n.text || n.desc).map((n) => `${n.text}|${n.desc}|${n.y1}`).join('\n');

// ── i18n data for the checks ────────────────────────────────────────────────
const flat = (o, p = '') => Object.entries(o).flatMap(([k, v]) => (v && typeof v === 'object' ? flat(v, `${p}${k}.`) : [[`${p}${k}`, String(v)]]));
const localeFile = (l) => JSON.parse(readFileSync(join(ROOT, 'src/i18n/locales', `${l}.json`), 'utf8'));
const EN = Object.fromEntries(flat(localeFile('en')));
const LOCALES = readdirSync(join(ROOT, 'src/i18n/locales')).filter((f) => f.endsWith('.json')).map((f) => f.replace('.json', ''));
const TRY_AGAIN = new Set(LOCALES.flatMap((l) => { const f = Object.fromEntries(flat(localeFile(l))); return [f['common.try_again'], f['common.retry']]; }).filter(Boolean).concat(['Try again', 'Retry']));
const GO_BACK = new Set(LOCALES.map((l) => Object.fromEntries(flat(localeFile(l)))['common.go_back_a11y']).filter(Boolean));
const LOC = LOCALE !== 'en' && LOCALES.includes(LOCALE) ? Object.fromEntries(flat(localeFile(LOCALE))) : null;
const LOC_VALUES = new Set(LOC ? Object.values(LOC) : []);
const EN_FUNCTION_WORDS = new Set(['the', 'your', 'you', 'to', 'and', 'of', 'this', 'that', 'is', 'are', 'for', 'with', 'from', 'when', 'what', 'will', 'can', "can't", "couldn't", "don't", "we", "our", 'it', 'on', 'in', 'a', 'an', 'or', 'not', 'no', 'yet', 'have', 'has', 'be', 'here', 'there', 'try', 'again']);
const enValueToKeys = new Map();
for (const [k, v] of Object.entries(EN)) { if (v.length >= 4) { if (!enValueToKeys.has(v)) enValueToKeys.set(v, []); enValueToKeys.get(v).push(k); } }

// The bar is drawn by TWO components with DIFFERENT label sources: QuickNavBar
// (non-tab screens) uses plain English literals by design (ui-playbook
// 2026-08-19), while the real tab bar uses t('nav.*'). So each slot accepts
// either spelling — a Dutch run flagged all 7 tab routes NO_NAVBAR against the
// English list (2026-09-16).
const TAB_SLOTS = [['Portfolio', 'nav.portfolio'], ['Market', 'nav.market'], ['Add', 'nav.add'], ['Events', 'nav.events'], ['Explore', 'nav.explore']];
const TABS = TAB_SLOTS.map(([literal]) => literal);
const tabAlternatives = (locale) => {
  const m = Object.fromEntries(flat(localeFile(locale)));
  return TAB_SLOTS.map(([literal, key]) => [literal, m[key]].filter(Boolean));
};
const TAB_ALTS = tabAlternatives(LOCALES.includes(LOCALE) ? LOCALE : 'en');
const RAW_PATTERNS = [
  [/\b\d{3,6} ?ms\b/, 'millisecond count'],
  [/\bfailed \(\d{3}\)|\b(GET|POST|PUT|PATCH|DELETE) \/[a-z]/, 'HTTP plumbing'],
  [/\bundefined\b/, 'undefined'],
  [/\bNaN\b/, 'NaN'],
  [/\[object /, '[object …]'],
  [/(TypeError|TimeoutError|ReferenceError|SyntaxError)\b/, 'exception name'],
  [/\{\{\s*\w+\s*\}\}/, 'uninterpolated {{var}}'],
  [/^[a-z][a-z0-9_]*(\.[a-z0-9_]+){1,3}$/, 'raw i18n key'],
  [/[€$£¥₩]-\d/, 'sign after currency (€-10)'],
];

// ── the checks ───────────────────────────────────────────────────────────────
function check(nodes, expect, W, H, focusLine, logs, DP) {
  const flags = [];
  const app = nodes.filter((n) => n.pkg === PKG);
  const visible = (n) => n.x2 > n.x1 && n.y2 > n.y1;
  // Bands in DP, not a fraction of the screen: 19% of a 2400px screen is a
  // header, 19% of a 1520px one cuts above the title — which flagged 7 screens
  // NO_TITLE on the 360dp round while their titles were plainly visible.
  const headerPx = 210 * DP;   // status bar + native header + a body title row
  const bottomPx = 110 * DP;   // the tab bar
  const header = app.filter((n) => visible(n) && n.y2 <= headerPx);
  const bottom = app.filter((n) => visible(n) && n.y1 >= H - bottomPx);
  const isGlyph = (s) => /^[\uE000-\uF8FF\s]*$/.test(s);
  const isClock = (s) => /^\d{1,2}:\d{2}$/.test(s);

  if (!focusLine.includes(PKG)) flags.push(['FOCUS', focusLine.replace(/.*mCurrentFocus=/, '').slice(0, 90)]);
  if (logs.fatal) flags.push(['CRASH', logs.fatal]);
  if (isLoading(nodes)) flags.push(['STILL_LOADING', `a spinner/skeleton is still on screen after ${TIMEOUT_S}s`]);
  if (logs.slowAt) flags.push(['SLOW_LOAD', `loading indicator still up at ${logs.slowAt}s (budget ${SPINNER_BUDGET_S}s)`]);

  // `!/^\d+$/`: the bell's unread BADGE ("2") sits in the header band, so it was
  // being reported as the screen's title — `settings` came back titled "2" and
  // NO_TITLE passed on a badge (2026-09-17). A count is never a title.
  const titleNode = header.find((n) => n.text && !isGlyph(n.text) && !isClock(n.text) && !/^\d+$/.test(n.text.trim()) && !/^Search\b|\.\.\.$|…$/.test(n.text));
  // A centred failure message with Try again IS the screen's heading (event
  // detail, offer, sponsor dashboard on 2026-09-15) — not a missing title.
  const failureState = app.some((n) => TRY_AGAIN.has(n.text) || TRY_AGAIN.has(n.desc));
  if (expect.title && !titleNode && !failureState) flags.push(['NO_TITLE', 'no text in the header band']);
  if (expect.back && !app.some((n) => GO_BACK.has(n.desc) || GO_BACK.has(n.text))) flags.push(['NO_BACK', 'no "Go back" control']);
  if (expect.cluster && !(header.some((n) => /^Notifications/.test(n.desc)) && header.some((n) => n.desc === 'Settings'))) flags.push(['NO_CLUSTER', 'bell/gear cluster missing']);
  if (expect.navbar) {
    const labels = new Set(bottom.flatMap((n) => [n.text, n.desc]).filter(Boolean));
    const missing = TAB_ALTS.filter((alts) => !alts.some((a) => labels.has(a))).map((alts) => alts[0]);
    if (missing.length) flags.push(['NO_NAVBAR', `missing: ${missing.join(', ')}`]);
  }
  for (const n of app) {
    for (const s of [n.text, n.desc]) {
      if (!s || isGlyph(s)) continue;
      if (expect.rawText !== false) for (const [re, what] of RAW_PATTERNS) if (re.test(s)) flags.push(['RAW_TEXT', `${what}: "${s.slice(0, 80)}"`]);
      // Hard-coded English never enters en.json, so the key comparison below
      // cannot see it — and that is most of the i18n backlog. A sentence with
      // several English function words that is not a value in this locale's
      // file is very likely untranslated. (Brand/product names are single
      // words or lack the function words, so they do not trip it.)
      if (LOC && !LOC_VALUES.has(s)) {
        const words = s.toLowerCase().match(/[a-z']+/g) || [];
        const hits = words.filter((w) => EN_FUNCTION_WORDS.has(w)).length;
        if (words.length >= 3 && hits >= 2) flags.push(['LIKELY_ENGLISH', `"${s.slice(0, 70)}"`]);
      }
      if (LOC && enValueToKeys.has(s)) {
        const keys = enValueToKeys.get(s);
        if (keys.some((k) => LOC[k] && LOC[k] !== s)) flags.push(['UNTRANSLATED', `"${s.slice(0, 60)}" (${keys[0]})`]);
      }
    }
  }
  if (logs.errors.length) flags.push(['JS_ERRORS', `${logs.errors.length} error line(s): ${logs.errors[0].slice(0, 120)}`]);
  // one flag per (kind, detail)
  const seen = new Set();
  return { title: titleNode?.text ?? null, flags: flags.filter(([k, d]) => (seen.has(k + d) ? false : seen.add(k + d))) };
}

// ── fixtures ─────────────────────────────────────────────────────────────────
async function resolveFixtures(inventory) {
  const fx = { ...inventory.static };
  const file = arg('fixtures', null);
  if (file) Object.assign(fx, JSON.parse(readFileSync(file, 'utf8')));
  const { SUPABASE_URL, SUPABASE_ANON_KEY, WALK_EMAIL, WALK_PASSWORD } = process.env;
  const url = SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL;
  const key = SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key || !WALK_EMAIL || !WALK_PASSWORD) {
    console.log('fixtures: Supabase/walk credentials not set — dynamic routes without --fixtures will be SKIPPED');
    return fx;
  }
  const tok = await fetch(`${url}/auth/v1/token?grant_type=password`, { method: 'POST', headers: { apikey: key, 'Content-Type': 'application/json' }, body: JSON.stringify({ email: WALK_EMAIL, password: WALK_PASSWORD }) }).then((r) => r.json());
  if (!tok.access_token) { console.log('fixtures: sign-in failed —', tok.error_description || tok.msg || 'unknown'); return fx; }
  const uid = tok.user.id;
  fx.userId ??= uid;
  const q = async (path) => {
    const r = await fetch(`${url}/rest/v1/${path}`, { headers: { apikey: key, Authorization: `Bearer ${tok.access_token}` } });
    if (!r.ok) return null;
    const rows = await r.json();
    return Array.isArray(rows) && rows[0] ? rows[0].id : null;
  };
  const today = new Date().toISOString().slice(0, 10);
  const pairs = {
    itemId: `items?select=id&user_id=eq.${uid}&limit=1`,
    listingId: `marketplace_listings?select=id&user_id=eq.${uid}&limit=1`,
    dealId: `mandate_deals?select=id&user_id=eq.${uid}&limit=1`,
    projectId: `build_paint_projects?select=id&user_id=eq.${uid}&limit=1`,
    offerId: `p2p_offers?select=id&or=(buyer_id.eq.${uid},seller_id.eq.${uid})&limit=1`,
    eventId: `events?select=id&is_public=eq.true&status=eq.published&date=gte.${today}&order=date.asc&limit=1`,
    ownEventId: `events?select=id&created_by=eq.${uid}&limit=1`,
  };
  for (const [name, path] of Object.entries(pairs)) {
    if (fx[name]) continue;
    const id = await q(path);
    if (id) fx[name] = id;
  }
  console.log(`fixtures: resolved ${Object.keys(pairs).filter((k) => fx[k]).join(', ') || 'none'} as ${WALK_EMAIL}`);
  return fx;
}

// ── inventory vs the file tree ──────────────────────────────────────────────
function appRoutes() {
  const out = [];
  const walk = (d) => { for (const e of readdirSync(d)) { const f = join(d, e); if (statSync(f).isDirectory()) walk(f); else if (e.endsWith('.tsx') && !e.startsWith('_layout') && !e.startsWith('+')) out.push(relative(join(ROOT, 'app'), f).replace(/\.tsx$/, '')); } };
  walk(join(ROOT, 'app'));
  return out;
}

// ── run ──────────────────────────────────────────────────────────────────────
const inventory = JSON.parse(readFileSync(join(ROOT, 'scripts/walk/routes.json'), 'utf8'));
const listed = new Set(inventory.routes.map((r) => r.route));
const unlisted = appRoutes().filter((r) => !listed.has(r));
const fixtures = await resolveFixtures(inventory);

mkdirSync(join(OUT, 'shots'), { recursive: true });
mkdirSync(join(OUT, 'dumps'), { recursive: true });

const restore = [];
if (SMALL) { sh('wm size 720x1520'); sh('wm density 320'); restore.push(() => { sh('wm size reset', { allowFail: true }); sh('wm density reset', { allowFail: true }); }); }
const cleanup = () => { for (const f of restore.reverse()) f(); };  // SIGINT path (sync steps only)
// Read AFTER --small is applied. `wm size` prints "Physical size" and, when
// overridden, "Override size" — the override is what the app lays out against.
// px per dp, so the header/tab bands mean the same thing on any screen.
const densityOut = sh('wm density');
const DP = (Number((densityOut.match(/Override density: (\d+)/) || densityOut.match(/Physical density: (\d+)/) || [0, 420])[1]) || 420) / 160;
const wmSize = sh('wm size');
const [W, H] = ((wmSize.match(/Override size: (\d+)x(\d+)/) || wmSize.match(/Physical size: (\d+)x(\d+)/)) || [0, 1080, 2400]).slice(1).map(Number);
process.on('SIGINT', () => { cleanup(); process.exit(130); });

// ── app language (the --locale state) ───────────────────────────────────────
// `cmd locale set-app-locales` does NOT reach this app (no android:localeConfig;
// proven 2026-09-15: a "nl" run rendered English) and the emulator is a `user`
// build, so the system locale cannot be set without root. The app's own
// Settings → Language picker is LOCAL-ONLY (updateSettings → AsyncStorage
// '@settings', no server write — AppearanceSection.handleLanguageChange), so
// the sweep sets it through the UI and restores "System default" afterwards.
// This is the ONE place the sweep taps anything.
const LANGUAGE_LABEL = { en: 'English', nl: 'Nederlands', de: 'Deutsch', fr: 'Français', es: 'Español', ja: '日本語', ko: '한국어' };
const SETTINGS_LANGUAGE = new Set(LOCALES.map((l) => Object.fromEntries(flat(localeFile(l)))['settings.language']).filter(Boolean));
const tapNode = (n) => sh(`input tap ${Math.round((n.x1 + n.x2) / 2)} ${Math.round((n.y1 + n.y2) / 2)}`);
async function setAppLanguage(optionLabel, expectRowLabel) {
  sh(`am start -a android.intent.action.VIEW -d 'sparrow://settings' ${PKG} >/dev/null 2>&1`, { allowFail: true });
  await sleep(8000);
  let row = null;
  for (let i = 0; i < 16 && !row; i++) {
    row = parseNodes(dumpXml()).find((n) => SETTINGS_LANGUAGE.has(n.desc) && n.y2 > n.y1);
    if (!row) { sh('input swipe 540 1700 540 900 400'); await sleep(1200); }
  }
  if (!row) throw new Error('language: Settings → Language row not found');
  tapNode(row);
  await sleep(2000);
  const opt = parseNodes(dumpXml()).find((n) => n.desc === optionLabel && n.y2 > n.y1);
  if (!opt) throw new Error(`language: option "${optionLabel}" not found in the picker`);
  tapNode(opt);
  await sleep(2000);
  if (expectRowLabel) {
    // POLL: the row needs a re-render, and a single check 2 s after the tap
    // failed on a fresh install while the language HAD applied (2026-09-16).
    let applied = false;
    for (let i = 0; i < 6 && !applied; i++) {
      applied = parseNodes(dumpXml()).some((n) => n.desc === expectRowLabel || n.text === expectRowLabel);
      if (!applied) await sleep(2000);
    }
    if (!applied) throw new Error(`language: "${optionLabel}" did not apply (row never read "${expectRowLabel}") — aborting rather than reporting English as untranslated`);
  }
}

// Wait for the APP, not a fixed delay: a deep link sent while the app is still
// booting is swallowed and the screen stays on Home (seen 2026-09-16: a
// "catalog-item" capture was Home's loading skeleton). Ready = the tab bar.
const coldStart = async () => {
  sh(`am force-stop ${PKG}`);
  await sleep(1500);
  sh(`monkey -p ${PKG} -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1`, { allowFail: true });
  const t0 = Date.now();
  await sleep(6000);
  while (Date.now() - t0 < 45000) {
    const labels = new Set(parseNodes(dumpXml()).map((n) => n.text || n.desc));
    if (TABS.every((t) => labels.has(t))) break;
    await sleep(2000);
  }
  await sleep(2000);
};
// Home's own header. A route that should not be Home but shows this landed wrong.
const looksLikeHome = (xml) => xml.includes('COLLECTION VALUE');

const results = [];
let sinceRestart = 0;
// The settled signature of the route walked BEFORE this one. A route whose
// screen is identical to it was never reached (2026-09-17).
let prevRouteSig = null;
try {
  await coldStart();
  if (LOC) {
    await setAppLanguage(LANGUAGE_LABEL[LOCALE], LOC['settings.language']);
    console.log(`language: app set to ${LANGUAGE_LABEL[LOCALE]} (verified)`);
    restore.push(async () => { try { await setAppLanguage('System default'); console.log('language: restored System default'); } catch (e) { console.log(`⚠️ language NOT restored: ${e.message} — set Settings → Language → System default by hand`); } });
  }
  for (const r of inventory.routes) {
    if (ONLY && !ONLY.split(',').some((o) => r.route.includes(o))) continue;
    const expect = { ...inventory.defaults, ...(r.expect || {}) };
    if (r.signedOut && !SIGNED_OUT) { results.push({ route: r.route, skipped: r.skip }); continue; }
    if (r.skip && !(r.signedOut && SIGNED_OUT)) { results.push({ route: r.route, skipped: r.skip }); continue; }
    const missing = (r.url.match(/\{(\w+)\}/g) || []).map((m) => m.slice(1, -1)).filter((k) => !fixtures[k]);
    if (missing.length) { results.push({ route: r.route, skipped: `no fixture: ${missing.join(', ')}` }); continue; }
    const url = r.url.replace(/\{(\w+)\}/g, (_, k) => encodeURIComponent(fixtures[k]));

    if (sinceRestart >= RESTART_EVERY) { await coldStart(); sinceRestart = 0; }
    sinceRestart++;
    const slug = r.route.replace(/[()[\]]/g, '').replace(/\//g, '__') || 'root';
    process.stdout.write(`${r.route.padEnd(36)} `);

    // ONE ROUTE MUST NOT KILL THE ROUND (2026-09-17). A hung `adb` at route 12
    // of 79 threw out of the loop and the process exited with no report at all:
    // eleven routes walked, nothing written, nothing to review. Whatever one
    // route does to adb, the round continues and says so in its own row.
    try {

    sh('logcat -c', { allowFail: true });
    // single-quote the URL on the device: `&` is a shell separator there (ANDROID_LAUNCH gotcha 11)
    sh(`am start -a android.intent.action.VIEW -d '${url}' ${PKG} >/dev/null 2>&1`, { allowFail: true });

    // Wait policy: ONE dump at the spinner budget. Nothing loading → one
    // confirming dump and done (most screens: ~2 dumps). Still loading → that is
    // SLOW_LOAD, and we keep waiting (cheaply) until it settles or TIMEOUT_S.
    const t0 = Date.now();
    const elapsed = () => (Date.now() - t0) / 1000;
    const homeIsRight = r.route === '(tabs)/index' || r.redirect;
    await sleep(SPINNER_BUDGET_S * 1000);
    let xml = dumpXml();
    let nodes = parseNodes(xml);
    let wrongScreen = false;
    let staleScreen = false;
    if (!homeIsRight && looksLikeHome(xml)) {
      // The deep link was swallowed — send it once more before judging anything.
      sh(`am start -a android.intent.action.VIEW -d '${url}' ${PKG} >/dev/null 2>&1`, { allowFail: true });
      await sleep(SPINNER_BUDGET_S * 1000);
      xml = dumpXml(); nodes = parseNodes(xml);
      wrongScreen = looksLikeHome(xml);
    }
    let slowAt = null;
    // An empty dump means uiautomator never saw the UI idle within the cap —
    // something is still animating, which at the budget is SLOW_LOAD too.
    if (isLoading(nodes) || !xml) slowAt = Math.round(elapsed());
    let prev = signature(nodes);
    while (elapsed() < TIMEOUT_S) {
      await sleep(isLoading(nodes) || !xml ? 1500 : 500);
      // Never let one dump run past the route's budget.
      xml = dumpXml(Math.min(DUMP_CAP_S, TIMEOUT_S - elapsed()));
      nodes = parseNodes(xml);
      const sig = signature(nodes);
      // "Stable" is not "arrived". The old condition was two matching dumps,
      // and a screen that has NOT STARTED navigating is perfectly stable — so
      // this loop used to exit on the PREVIOUS route's screen and judge that
      // (2026-09-17: `add-manual` was judged on `l/[id]`'s tree while its own
      // screenshot, taken later, showed the right screen). A settled screen
      // that is still byte-identical to the one the last route left behind is
      // not this route's screen yet; keep waiting for it to change.
      const arrived = !prevRouteSig || sig !== prevRouteSig || homeIsRight;
      if (sig && sig === prev && !isLoading(nodes) && arrived) break;
      prev = sig;
    }
    // Still the previous route's screen after the whole budget: the link never
    // took. Re-send once (exactly as the Home case does), then refuse to judge
    // someone else's screen rather than report it `ok` — round 6 reported
    // `analytics` ok on a tree whose title was literally "Add manually".
    if (!wrongScreen && !homeIsRight && xml && prevRouteSig && signature(nodes) === prevRouteSig) {
      sh(`am start -a android.intent.action.VIEW -d '${url}' ${PKG} >/dev/null 2>&1`, { allowFail: true });
      await sleep(SPINNER_BUDGET_S * 1000);
      const xml2 = dumpXml();
      if (xml2) {
        const nodes2 = parseNodes(xml2);
        if (signature(nodes2) === prevRouteSig) staleScreen = true;
        else { xml = xml2; nodes = nodes2; }
      } else staleScreen = true;
    }
    const settleS = Math.round(elapsed());
    // A screenshot is EVIDENCE, not the round. `adb exec-out screencap` hung on
    // 2026-09-17 with a second emulator running on the same machine, the 60 s
    // default timeout threw, and the whole round died at route 12 of 79 with no
    // report written — 11 routes' work lost to a picture. Capped, non-fatal, and
    // recorded as missing if it fails.
    const png = adb(['exec-out', 'screencap', '-p'], { binary: true, allowFail: true, timeout: 25 });
    let shotOk = false;
    if (png && png.length > 1000) { writeFileSync(join(OUT, 'shots', `${slug}.png`), png); shotOk = true; }
    // The loop's last dump IS the settled screen — no third slow dump, unless
    // it capped out, in which case one more try before judging an empty tree.
    // Capped dumps all came back empty: the UI never went idle within 10 s. One
    // long dump (30 s) so the screen still gets its checks, and NOT_IDLE says
    // that something keeps animating — itself worth a look (a spinner or
    // shimmer still running after the screen has settled on a failure).
    let notIdle = false;
    if (!xml) { notIdle = true; xml = dumpXml(30); nodes = parseNodes(xml); }
    writeFileSync(join(OUT, 'dumps', `${slug}.xml`), xml);
    const log = sh(`logcat -d -v brief ReactNativeJS:E AndroidRuntime:E '*:S'`, { allowFail: true }) || '';
    const errors = log.split('\n').filter((l) => l.startsWith('E/ReactNativeJS'));
    const fatalBlock = log.includes('FATAL EXCEPTION') && log.includes(`Process: ${PKG}`);
    const logs = { slowAt, errors, fatal: fatalBlock ? (log.split('\n').find((l) => /Exception|Error/.test(l) && !l.includes('FATAL')) || 'FATAL EXCEPTION').slice(0, 160) : null };

    const res = wrongScreen
      ? { title: null, flags: [['WRONG_SCREEN', 'still on Home after re-sending the deep link — route not reached, not judged']] }
      : staleScreen
      ? { title: null, flags: [['SAME_AS_PREVIOUS', 'screen is identical to the previous route after re-sending the deep link — route not reached, not judged']] }
      : !xml
      // No tree to check: say THAT, instead of reporting NO_TITLE/NO_NAVBAR on nothing.
      ? { title: null, flags: [['NO_DUMP', `uiautomator never saw the UI idle (${DUMP_CAP_S}s cap, twice) — something keeps animating; see the screenshot`]] }
      : r.redirect
      ? { title: null, flags: focus().includes(PKG) ? [] : [['FOCUS', 'not in the app after redirect']] }
      : check(nodes, expect, W, H, focus(), logs, DP);
    // A chrome flag can be a CAPTURE artefact: the loop's last dump can land
    // mid-render (2026-09-16: `listings` was flagged NO_NAVBAR from a 15-node
    // tree while the screenshot, taken later, showed the bar). Re-dump once and
    // re-check before believing it.
    const CHROME = ['NO_NAVBAR', 'NO_TITLE', 'NO_CLUSTER', 'NO_BACK'];
    if (!wrongScreen && xml && res.flags.some(([k]) => CHROME.includes(k))) {
      const xml2 = dumpXml();
      if (xml2) {
        const res2 = check(parseNodes(xml2), expect, W, H, focus(), logs, DP);
        if (res2.flags.filter(([k]) => CHROME.includes(k)).length < res.flags.filter(([k]) => CHROME.includes(k)).length) {
          writeFileSync(join(OUT, 'dumps', `${slug}.xml`), xml2);
          res.title = res2.title; res.flags = res2.flags;
        }
      }
    }
    if (notIdle && xml) res.flags.push(['NOT_IDLE', `UI never idle within ${DUMP_CAP_S}s — something keeps animating`]);
    // Only a screen we actually reached becomes the baseline for the next route;
    // otherwise one swallowed link would excuse the next route as well.
    if (xml && !wrongScreen && !staleScreen) prevRouteSig = signature(nodes);
    if (logs.fatal) { res.flags.push(['CRASH', logs.fatal]); await coldStart(); sinceRestart = 0; }
    const real = res.flags.filter(([k]) => k !== 'JS_ERRORS');
    console.log(`${real.length ? real.map(([k]) => k).join(' ') : 'ok'}  (${settleS}s)`);
    if (!shotOk) res.flags.push(['NO_SHOT', 'screencap timed out — the checks below ran on the dump, but there is no picture to review']);
    results.push({ route: r.route, url, redirect: !!r.redirect, why: r.why, settleS, shot: shotOk ? `shots/${slug}.png` : null, ...res });
    } catch (e) {
      // Recorded as a finding, not swallowed: a route nobody could walk is not
      // a route that passed.
      console.log(`TOOL_ERROR  (${e.message.slice(0, 80)})`);
      results.push({ route: r.route, url, redirect: !!r.redirect, why: r.why, settleS: null, shot: null, title: null,
        flags: [['TOOL_ERROR', `the sweep itself failed on this route: ${e.message.slice(0, 160)}`]] });
      // The device may be wedged; a cold start is the cheapest way back to a
      // known state before the next route.
      try { await coldStart(); sinceRestart = 0; } catch { /* the finally block reports the round either way */ }
    }
  }
} finally {
  for (const f of restore.reverse()) await f();
  restore.length = 0;
}

// ── report ───────────────────────────────────────────────────────────────────
const walked = results.filter((r) => !r.skipped);
// A flag on most screens is ONE finding about shared chrome (the header
// cluster's English a11y labels, QuickNavBar's literal tab names), not 79.
// Pull those out once so the per-screen cards show what is specific to a screen.
const flagCount = new Map();
for (const r of walked) for (const [k, d] of new Map(r.flags.map((f) => [f.join('|'), f])).values()) { const key = `${k}|${d}`; flagCount.set(key, (flagCount.get(key) || 0) + 1); }
const repeated = [...flagCount.entries()].filter(([key, n]) => !key.startsWith('JS_ERRORS') && n >= 5 && n >= walked.length * 0.4).map(([key, n]) => ({ kind: key.split('|')[0], detail: key.slice(key.indexOf('|') + 1), screens: n }));
const repeatedKeys = new Set(repeated.map((x) => `${x.kind}|${x.detail}`));
for (const r of walked) r.flags = r.flags.filter(([k, d]) => !repeatedKeys.has(`${k}|${d}`));
const flagged = walked.filter((r) => r.flags.some(([k]) => k !== 'JS_ERRORS'));
const byKind = {};
for (const r of walked) for (const [k] of r.flags) byKind[k] = (byKind[k] || 0) + 1;
const report = { repeated, label: LABEL, locale: LOCALE, small: SMALL, at: new Date().toISOString(), device: `${W}x${H}`, total: inventory.routes.length, walked: walked.length, skipped: results.filter((r) => r.skipped).length, flagged: flagged.length, byKind, unlisted, results };
writeFileSync(join(OUT, 'report.json'), JSON.stringify(report, null, 2));

const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
const card = (r) => r.skipped
  ? `<div class="card skip"><div class="route">${esc(r.route)}</div><div class="why">SKIPPED — ${esc(r.skipped)}</div></div>`
  : `<div class="card ${r.flags.some(([k]) => k !== 'JS_ERRORS') ? 'bad' : 'ok'}"><a href="${r.shot}"><img loading="lazy" src="${r.shot}" alt="${esc(r.route)}"></a>
     <div class="route">${esc(r.route)}${r.redirect ? ' <span class="tag">redirect</span>' : ''}</div>
     <div class="meta">title: ${esc(r.title ?? '—')} · ${r.settleS}s</div>
     <ul>${r.flags.map(([k, d]) => `<li class="${k === 'JS_ERRORS' ? 'info' : 'flag'}"><b>${k}</b> ${esc(d)}</li>`).join('')}</ul></div>`;
writeFileSync(join(OUT, 'index.html'), `<!doctype html><meta charset="utf-8"><title>Sweep ${esc(LABEL)} ${esc(report.at)}</title>
<style>body{font:13px system-ui;margin:16px;background:#f6f7f8;color:#111}h1{font-size:18px}.sum{margin:8px 0 16px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}.card{background:#fff;border:1px solid #ddd;border-radius:10px;padding:8px}
.card.bad{border-color:#d33}.card.skip{opacity:.6}img{width:100%;border-radius:6px;border:1px solid #eee}.route{font-weight:700;margin-top:6px}
.meta,.why{color:#666;font-size:12px}ul{padding-left:16px;margin:6px 0}.flag{color:#b00}.info{color:#777}.tag{background:#eef;border-radius:4px;padding:0 4px;font-weight:400}</style>
<h1>Screen sweep — ${esc(LABEL)} · locale ${esc(LOCALE)}${SMALL ? ' · small' : ''} · ${esc(report.at)}</h1>
<div class="sum">walked ${report.walked}/${report.total} · flagged ${report.flagged} · skipped ${report.skipped} · ${Object.entries(byKind).map(([k, v]) => `${k} ${v}`).join(' · ')}${unlisted.length ? ` · <b class="flag">UNLISTED: ${esc(unlisted.join(', '))}</b>` : ''}</div>
${repeated.length ? `<h2 style="font-size:15px">Repeated across screens (one finding each)</h2><ul>${repeated.map((x) => `<li class="flag"><b>${x.kind}</b> ${esc(x.detail)} — on ${x.screens} screens</li>`).join('')}</ul>` : ''}
<div class="grid">${[...results].sort((a, b) => (a.skipped ? 2 : a.flags?.some(([k]) => k !== 'JS_ERRORS') ? 0 : 1) - (b.skipped ? 2 : b.flags?.some(([k]) => k !== 'JS_ERRORS') ? 0 : 1)).map(card).join('\n')}</div>`);

console.log(`\nwalked ${report.walked}/${report.total}, flagged ${report.flagged}, skipped ${report.skipped}`);
for (const x of repeated) console.log(`  repeated on ${x.screens} screens: ${x.kind} ${x.detail}`);
console.log(Object.entries(byKind).map(([k, v]) => `  ${k}: ${v}`).join('\n'));
if (unlisted.length) console.log(`UNLISTED routes (add to scripts/walk/routes.json): ${unlisted.join(', ')}`);
console.log(`contact sheet: ${join(OUT, 'index.html')}`);
