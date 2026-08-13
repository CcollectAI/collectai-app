#!/usr/bin/env node
/**
 * Every pushed screen must offer a way back.
 *
 * `app/_layout.tsx` sets `headerShown: true` globally, so a route inherits the
 * native header and its back chevron for free. A screen only becomes a dead end
 * when it turns that off and does not replace it — and that is invisible at the
 * call site, because the screen looks complete in isolation.
 *
 * Tab ROOTS are exempt and must stay exempt: you cannot go "back" from a tab,
 * and a chevron there would be the only one of its kind in the app
 * (`app/(tabs)/marketplace.tsx` renders `/listings` with `asTab` precisely to
 * suppress it). This checker encodes that distinction rather than demanding a
 * back button everywhere, which would be the wrong rule.
 *
 * Related but different gate: `check:back` (scripts/check-unguarded-back.mjs)
 * asks whether a back handler is SAFE (`safeGoBack`, not a bare
 * `router.back()`). This one asks whether the handler EXISTS at all.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const APP = 'app';

/** Route files that are legitimately without a back control. */
function isExempt(rel) {
  return (
    rel.includes('_layout') ||
    // Tab roots: no stack to pop.
    /^app\/\(tabs\)\//.test(rel) ||
    // Auth flow manages its own navigation and must never fall back into tabs.
    /^app\/\(auth\)\//.test(rel) ||
    // Not a screen.
    rel.endsWith('+not-found.tsx') ||
    rel.endsWith('+html.tsx')
  );
}

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (p.endsWith('.tsx')) out.push(p);
  }
  return out;
}

const offenders = [];
let checked = 0;
let inherited = 0;

for (const file of walk(APP)) {
  const rel = relative('.', file).replace(/\\/g, '/');
  if (isExempt(rel)) continue;
  const src = readFileSync(file, 'utf8');
  checked += 1;

  const hidesHeader = /headerShown\s*:\s*false/.test(src);
  if (!hidesHeader) {
    // Inherits the global native header, which carries a back chevron.
    inherited += 1;
    continue;
  }

  // Header suppressed — something else has to provide the way back.
  const hasOwnBack =
    /<ScreenHeader\b(?![^>]*showBack\s*=\s*\{\s*false\s*\})/.test(src) ||
    /safeGoBack\s*\(/.test(src) ||
    /headerLeft\s*:/.test(src) ||
    /name=["'](chevron-back|arrow-back)["']/.test(src);

  if (!hasOwnBack) offenders.push(rel);
}

if (offenders.length) {
  console.error(
    `[back-affordance] FAIL — ${offenders.length} screen(s) hide the header and provide no way back:`,
  );
  for (const o of offenders) console.error(`  ${o}`);
  console.error(
    '\nEither drop `headerShown: false`, or render <ScreenHeader /> ' +
      '(showBack defaults to true), or add a headerLeft that calls safeGoBack.',
  );
  process.exit(1);
}

console.log(
  `[back-affordance] PASS — ${checked} pushed screen(s): ${inherited} inherit the native header, ` +
    `${checked - inherited} suppress it and provide their own back control.`,
);
