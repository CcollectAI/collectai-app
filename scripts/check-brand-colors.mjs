#!/usr/bin/env node
/**
 * Gate: never hardcode a label colour on a fill that INVERTS with the palette.
 *
 * Why this exists
 * ---------------
 * docs/ui-playbook.md, "Never hardcode a colour on a themed background". The
 * app has four palettes and `accent` is not always dark:
 *
 *   palette              accent      accentText   white-on-accent contrast
 *   light                #40C9C6     #FFFFFF      2.02:1   ⚠ fails 4.5:1 AND 3:1
 *   dark                 #40C9C6     #FFFFFF      2.02:1   ⚠ same token both ways
 *   high-contrast light  #0052CC     #FFFFFF      6.82:1   ✓
 *   high-contrast DARK   #4DA6FF     #000000      8.21:1   ✓  <- BLACK label
 *
 * Read the values from `src/theme/useAppTheme.ts` and `src/theme/highContrast.ts`.
 * This table used to list #1fb6ff / #38bdf8, which are in `src/theme/colors.ts`
 * — a LegacyTheme whose only reader, `useColorTheme`, has no callers anywhere.
 * A gate documenting the dead palette teaches the wrong colour to whoever reads
 * it next (corrected 2026-09-17; the ratios above were computed, not eyeballed).
 *
 * ⚠ The light/dark rows are a real contrast failure, not a theming one, and it
 * is a BRAND decision rather than a bug this gate can fix: #40C9C6 is the
 * Tiffany accent. Dark ink on it clears 4.5:1 (#0B3B39 → 6.11:1); so does a
 * darker fill under white (#0A7A77 → 5.17:1). Using `accentText` — which this
 * gate enforces — is what makes that decision a ONE-LINE change instead of a
 * 300-call-site sweep.
 *
 * `app/subscription.tsx` hardcoded white on a `brand.darker` button, and in
 * high-contrast dark that palette makes `brand.darker` literally `#FFFFFF` —
 * white text on a white button, with the spinner inside it vanishing the same
 * way. The primary CTA of the paywall was invisible (fixed 2026-07-28).
 *
 * The sweep on 2026-08-19 found the app carries 858 hex literals, 470 of them
 * in files that legitimately DEFINE colour (the palettes, the 54 category
 * tints, franchise colours). Flagging all 388 remaining would be noise — most
 * are on fixed scrims, camera overlays and photo gradients where nothing
 * inverts. This checks the ONE pattern that actually breaks:
 *
 *   a hardcoded `color:` / `tintColor:` literal, within a few lines of a
 *   `backgroundColor` set from a THEME token.
 *
 * Three live instances were found and fixed; one was correctly left alone (see
 * ALLOWLIST), which is the case worth remembering — the naive fix there makes
 * it worse.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname;

/**
 * Sites that hardcode deliberately, each with the reason it is safe. A bare
 * path is not enough — the point of the entry is the argument.
 */
const ALLOWLIST = new Map([
  ['src/components/Button.tsx',
   'The `danger` variant. `colors.danger` is red in ALL FOUR palettes ' +
   '(#EF4444 / #CC0000 / #FF4444), so white always has contrast on it — while ' +
   '`accentText` is #000000 in high-contrast dark, which would put BLACK ON ' +
   'RED and make it worse. The rule is about a fill that INVERTS; this one ' +
   'does not.'],
]);

/** Files that define the palette rather than consume it. */
const PALETTE = ['src/theme/', 'src/ui/theme.ts', 'src/constants/colors.ts'];

// Near-white and near-black are the literals that stop working when the
// palette flips. A mid-tone on a themed fill is a design choice, not a bug.
const RISKY = /#(fff(fff)?|FFF(FFF)?|000(000)?|fefefe)\b/i;

// A fill taken from the theme — i.e. one that changes with the palette.
const THEMED_FILL =
  /backgroundColor:\s*(colors\.|theme\.|tokens\.brand|BRAND_COLORS)/;

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
for (const file of [...walk(join(ROOT, 'app')), ...walk(join(ROOT, 'src'))]) {
  const rel = relative(ROOT, file);
  if (rel.includes('__tests__')) continue;
  if (PALETTE.some((p) => rel.startsWith(p))) continue;
  if (ALLOWLIST.has(rel)) continue;

  const lines = readFileSync(file, 'utf8').split('\n');
  lines.forEach((line, i) => {
    const t = line.trim();
    if (t.startsWith('//') || t.startsWith('*') || t.startsWith('/*')) return;
    // TWO spellings, and only the first was checked until 2026-09-17:
    //   style form  →  color: '#fff'          (StyleSheet / inline object)
    //   JSX form    →  color="#fff"  color={'#fff'}   (Ionicons, Feather, Image)
    // The app is full of icon components that take the colour as a PROP, so the
    // gate was blind to 43 hardcoded whites sitting on themed fills — including
    // the Deal Agent, the Inbox and the filter sheet (class sweep L).
    const styleForm = /(^|[\s{,])(color|tintColor):\s*["']#/.test(line);
    const jsxForm = /\b(color|tintColor)=\{?\s*["']#/.test(line);
    if (!styleForm && !jsxForm) return;
    if (!RISKY.test(line)) return;
    // The fill it sits on is declared nearby — but "nearby" has to survive a
    // COMMENT sitting between them. The first version used ±6 lines and went
    // green when the bug was reintroduced under a 4-line explanatory comment:
    // a gate that passes on the exact defect it was written for is worse than
    // no gate, because it is trusted. Proven by reintroducing it and watching
    // this go red.
    const window = lines.slice(Math.max(0, i - 16), i + 9).join('\n');
    if (!THEMED_FILL.test(window)) return;
    findings.push({ at: `${rel}:${i + 1}`, line: t.slice(0, 100) });
  });
}

if (findings.length === 0) {
  console.log(
    `[brand-colors] PASS — no hardcoded label sits on a themed fill ` +
    `(${ALLOWLIST.size} documented exception).`);
  process.exit(0);
}

console.error('[brand-colors] FAIL — a hardcoded colour sits on a fill that inverts\n');
for (const f of findings) {
  console.error(`  ${f.at}`);
  console.error(`    ${f.line}\n`);
}
console.error(
  'Use `colors.accentText` for a label on `accent` or a `brand.*` fill. In\n' +
  'high-contrast dark the accent is LIGHT (#4DA6FF) and accentText is #000000,\n' +
  'so hardcoded white is invisible there. If the fill genuinely never inverts\n' +
  '(danger is red in every palette), add the file to ALLOWLIST WITH THE REASON.');
process.exit(1);
