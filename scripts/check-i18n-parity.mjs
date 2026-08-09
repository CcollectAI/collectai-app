#!/usr/bin/env node
/**
 * Fail when a locale is missing a key that `en.json` has.
 *
 * `src/i18n/index.ts` names en as the source of truth and sets
 * `fallbackLng: 'en'`, so a missing key does not crash and does not render a raw
 * key — it silently renders ENGLISH. That is why this went unnoticed: on a Dutch
 * device a third of the settings screen was in English and nothing anywhere said
 * so. Measured 2026-08-09: en had 597 keys, every other locale had 424.
 *
 * WHY THE EXISTING i18n CHECK DOES NOT CATCH IT
 *
 * `check-i18n-strings.mjs` finds user-visible strings that were never wrapped in
 * `t()`. That is the other half of the problem: it polices the CODE, and cannot
 * see a key that is wrapped correctly but absent from six of seven files. Two
 * different axes, so two checks.
 *
 * MISSING vs EXTRA
 *
 *   missing (in en, not in locale) -> FAILS. A user sees the wrong language.
 *   extra   (in locale, not in en) -> reported, does not fail. Dead weight from
 *                                     a key en dropped; harmless at runtime, and
 *                                     failing on it would block a legitimate
 *                                     en-side deletion until six files caught up.
 *
 * Compares FLATTENED paths (`settings.tax_reporting`), so a key nested at the
 * wrong depth counts as missing — which it effectively is, since `t()` addresses
 * it by path.
 *
 * Usage: node scripts/check-i18n-parity.mjs   (npm run i18n:parity)
 */
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const DIR = join(process.cwd(), 'src', 'i18n', 'locales');
const SOURCE = 'en.json';

/** Flatten to dotted paths, so depth mismatches are caught, not glossed over. */
function flatten(obj, prefix = '', out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) flatten(v, path, out);
    else out[path] = v;
  }
  return out;
}

const files = readdirSync(DIR).filter((f) => f.endsWith('.json'));
if (!files.includes(SOURCE)) {
  console.error(`✖ ${SOURCE} not found in ${DIR} — it is the source of truth.`);
  process.exit(1);
}

const source = flatten(JSON.parse(readFileSync(join(DIR, SOURCE), 'utf8')));
const sourceKeys = Object.keys(source);

const failures = [];
const notes = [];

for (const file of files.sort()) {
  if (file === SOURCE) continue;
  const locale = flatten(JSON.parse(readFileSync(join(DIR, file), 'utf8')));
  const missing = sourceKeys.filter((k) => !(k in locale));
  const extra = Object.keys(locale).filter((k) => !(k in source));

  // An untranslated string that is byte-identical to English is usually a real
  // translation (proper nouns, "OK", "Pokemon") — but a WHOLE FILE of them means
  // someone copied en.json and called it done, which is worth saying out loud.
  const identical = sourceKeys.filter((k) => k in locale && locale[k] === source[k]);
  const identicalPct = Math.round((identical.length / sourceKeys.length) * 100);

  if (missing.length) failures.push({ file, missing });
  if (extra.length) notes.push(`${file}: ${extra.length} key(s) not in ${SOURCE} (dead weight): ${extra.slice(0, 5).join(', ')}${extra.length > 5 ? ' …' : ''}`);
  if (identicalPct > 80) notes.push(`${file}: ${identicalPct}% of values are byte-identical to English — likely an unfilled copy.`);
}

if (failures.length) {
  console.error('\n✖ Locale(s) missing keys that en.json defines.');
  console.error('  fallbackLng is "en", so each of these renders ENGLISH to a user of that language —');
  console.error('  no crash, no raw key, nothing in the logs.\n');
  for (const { file, missing } of failures) {
    const byNamespace = {};
    for (const k of missing) {
      const ns = k.split('.')[0];
      byNamespace[ns] = (byNamespace[ns] || 0) + 1;
    }
    const summary = Object.entries(byNamespace)
      .sort((a, b) => b[1] - a[1])
      .map(([ns, n]) => `${ns}(${n})`)
      .join(' ');
    console.error(`  ${file} — ${missing.length} missing`);
    console.error(`      ${summary}`);
    console.error(`      e.g. ${missing.slice(0, 4).join(', ')}\n`);
  }
  for (const n of notes) console.error(`  note: ${n}`);
  console.error(`\nSource of truth: ${SOURCE} (${sourceKeys.length} keys).`);
  process.exit(1);
}

for (const n of notes) console.log(`ℹ ${n}`);
console.log(`✓ i18n parity — all ${files.length - 1} locale(s) define every one of `
  + `${sourceKeys.length} keys in ${SOURCE}.`);
