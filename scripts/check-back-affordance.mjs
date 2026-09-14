#!/usr/bin/env node
/**
 * Every pushed screen must offer a way back.
 *
 * `app/_layout.tsx` sets `headerShown: true` globally, so a route inherits the
 * root header and its safeGoBack chevron for free (the first check below makes
 * sure that chevron is ours, not the native one). A screen only becomes a dead end
 * when it turns that off and does not replace it — and that is invisible at the
 * call site, because the screen looks complete in isolation.
 *
 * Tab ROOTS are exempt and must stay exempt: you cannot go "back" from a tab,
 * so this checker does not DEMAND a back control there. (The Market tab shows
 * one anyway — `listings.tsx` renders it unconditionally since 2026-08-14, by
 * request — which is allowed, not required.)
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

// "Inherits the global header" only counts as a way back if the global header's
// back button is OURS. native-stack does not draw its own chevron at all when the
// stack is empty (push tap, cold deep link), so until 2026-09-14 this gate passed
// nine unregistered routes that opened with no back control. Require the
// navigator's DEFAULT screenOptions to carry a headerLeft, not just iconOnlyHeader.
{
  // Comments stripped FIRST: a brace inside a comment would unbalance the scan,
  // and a commented-out `// headerLeft:` must not count as present.
  const layout = readFileSync(join(APP, '_layout.tsx'), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1');
  const open = layout.indexOf('screenOptions={{');
  // Balanced-brace scan: the block contains nested `{ ... }` objects.
  let depth = 0;
  let end = -1;
  for (let i = open + 'screenOptions='.length; open >= 0 && i < layout.length; i++) {
    if (layout[i] === '{') depth += 1;
    else if (layout[i] === '}') {
      depth -= 1;
      if (depth === 0) { end = i; break; }
    }
  }
  const block = open >= 0 && end > 0 ? layout.slice(open, end) : '';
  if (!/headerLeft\s*:/.test(block)) {
    console.error(
      '[back-affordance] FAIL — the root <Stack screenOptions> in app/_layout.tsx has no ' +
        'headerLeft.\nEvery route that is not registered with iconOnlyHeader then gets the ' +
        'native back button, which is not drawn at all on an empty stack (push tap, cold ' +
        'deep link). Add `headerLeft: () => <HeaderBackButton />` to the defaults.',
    );
    process.exit(1);
  }
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
    // Inherits the root header, whose headerLeft was verified above.
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
  `[back-affordance] PASS — ${checked} pushed screen(s): ${inherited} inherit the root header (safe headerLeft), ` +
    `${checked - inherited} suppress it and provide their own back control.`,
);
