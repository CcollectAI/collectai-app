#!/usr/bin/env node
/**
 * Fail on an effect that CANCELS ITS OWN in-flight request.
 *
 * The shape:
 *
 *     useEffect(() => {
 *       if (!open || state !== 'idle') return;   // state used as a re-entry guard
 *       let cancelled = false;
 *       setState('loading');                     // <-- writes its own dependency
 *       fetchThing()
 *         .then((r) => { if (cancelled) return; setData(r); setState('ok'); })
 *         .catch(()  => { if (!cancelled) setState('error'); });
 *       return () => { cancelled = true; };      // <-- runs on the re-render
 *     }, [open, state]);                         // <-- dependency it just wrote
 *
 * `setState('loading')` re-renders, the dep array changes, React tears the
 * effect down, and the cleanup sets `cancelled = true` — all long before the
 * response lands. The `.then` and `.catch` then BOTH no-op, so the screen sits
 * on "Loading…" forever with no error, no log, and no retry reachable because
 * the error branch never renders. The request itself succeeded.
 *
 * A per-request timeout does not save you here: the fetch resolving is
 * irrelevant when the handler that would act on it has been disarmed. This is
 * why it is not covered by check-unbounded-awaits.mjs.
 *
 * Real instance: `app/offers.tsx` — the Add-tracking sheet's carrier picker was
 * dead for every seller on every open (found 2026-08-09, reported as "carriers
 * don't load"). The endpoint was healthy and returned 9 carriers to curl the
 * whole time, which is why reading the network layer found nothing.
 *
 * The rule: **a state value the effect itself writes can never be that
 * effect's own dependency.** Put the re-entry guard in a `useRef` (invisible to
 * the dep array) and drive an explicit retry with a separate nonce.
 *
 * Usage: node scripts/check-self-cancelling-effects.mjs   (npm run check:effects)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOTS = ['app', 'src'];
const EXTS = ['.tsx', '.ts'];

// Flags that mean "an async continuation is being disarmed on teardown".
const CANCEL_FLAGS = ['cancelled', 'canceled', 'ignore', 'ignored', 'aborted', 'stale', 'disposed'];

/**
 * Blank out comments and string/template literals, preserving byte offsets and
 * newlines so reported line numbers stay true.
 *
 * A regex-only version reads `'// not a comment'` as a comment and silently
 * stops scanning the rest of the line — a gate with a false negative is worse
 * than no gate (see check-unguarded-back.mjs, which learned this the hard way).
 */
function blankNonCode(src) {
  const out = src.split('');
  let i = 0;
  const n = src.length;
  const blank = (from, to) => {
    for (let k = from; k < to && k < n; k++) if (out[k] !== '\n') out[k] = ' ';
  };
  while (i < n) {
    const c = src[i];
    const c2 = src[i + 1];
    if (c === '/' && c2 === '/') {
      let j = i + 2;
      while (j < n && src[j] !== '\n') j++;
      blank(i, j);
      i = j;
    } else if (c === '/' && c2 === '*') {
      let j = i + 2;
      while (j < n && !(src[j] === '*' && src[j + 1] === '/')) j++;
      blank(i, Math.min(j + 2, n));
      i = j + 2;
    } else if (c === '"' || c === "'" || c === '`') {
      const quote = c;
      let j = i + 1;
      while (j < n) {
        if (src[j] === '\\') { j += 2; continue; }
        if (src[j] === quote) break;
        j++;
      }
      blank(i + 1, j);
      i = j + 1;
    } else {
      i++;
    }
  }
  return out.join('');
}

/** Index of the `}` matching the `{` at `open`, or -1. */
function matchBrace(src, open) {
  let depth = 0;
  for (let i = open; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

/**
 * Yield { body, deps, line } for every `useEffect(() => { ... }, [ ... ])`.
 * Brace-matched rather than regexed, so a nested closure in the body cannot end
 * the match early and hide a violation.
 */
function* effects(code) {
  const re = /useEffect\(\s*\(\s*\)\s*=>\s*\{/g;
  let m;
  while ((m = re.exec(code)) !== null) {
    const open = code.indexOf('{', m.index + 'useEffect('.length);
    const close = matchBrace(code, open);
    if (close === -1) continue;
    const after = code.slice(close + 1);
    const depsMatch = /^\s*,\s*\[([^\]]*)\]/.exec(after);
    if (!depsMatch) continue;
    yield {
      body: code.slice(open + 1, close),
      deps: depsMatch[1],
      line: code.slice(0, m.index).split('\n').length,
    };
  }
}

const offenders = [];
let parsed = 0;
let withCancelFlag = 0;
// Effects this parser cannot reach. Reported, not swallowed: "211 scanned" with no
// denominator reads as full coverage. Both known cases are concise-body effects
// (`useEffect(() => expr, [])`, `useEffect(() => () => {...})`) which cannot carry
// this bug — there is no block to start async work in — but the count has to be
// visible for that to be checkable rather than asserted.
let unparsed = 0;

function walk(dir) {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry.startsWith('.')) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) { walk(full); continue; }
    if (!EXTS.some((e) => entry.endsWith(e))) continue;

    const code = blankNonCode(readFileSync(full, 'utf8'));
    const occurrences = (code.match(/useEffect\(/g) || []).length;
    let matchedHere = 0;
    for (const { body, deps, line } of effects(code)) {
      matchedHere++;
      parsed++;
      const hasCancel = CANCEL_FLAGS.some((f) => new RegExp(`\\b${f}\\b`).test(body));
      if (!hasCancel) continue;
      withCancelFlag++;

      // State setters invoked inside the effect body: setFoo( -> "Foo".
      const setters = new Set([...body.matchAll(/\bset([A-Z]\w*)\s*\(/g)].map((x) => x[1]));
      const depList = deps.split(',').map((d) => d.trim()).filter(Boolean);
      for (const dep of depList) {
        if (!/^[a-z]\w*$/.test(dep)) continue;               // skip obj.prop, calls, refs
        const setterName = dep[0].toUpperCase() + dep.slice(1);
        if (setters.has(setterName)) {
          offenders.push({ file: relative(process.cwd(), full), line, dep, setterName });
        }
      }
    }
    unparsed += Math.max(0, occurrences - matchedHere);
  }
}

for (const root of ROOTS) walk(root);

if (offenders.length) {
  console.error('\n✖ Self-cancelling effect(s) — the effect tears itself down before its own response lands:\n');
  for (const o of offenders) {
    console.error(`  ${o.file}:${o.line}`);
    console.error(`      dependency \`${o.dep}\` is written by \`set${o.setterName}(…)\` inside the same effect,`);
    console.error(`      and the body disarms its async handler on teardown → the .then/.catch never run.`);
    console.error(`      Move the re-entry guard into a useRef and retry via a separate nonce.\n`);
  }
  console.error(`Scanned ${parsed} useEffect blocks (${withCancelFlag} with a cancellation flag, `
    + `${unparsed} concise-body effect(s) not parseable and out of scope).`);
  process.exit(1);
}

console.log(`✓ No self-cancelling effects (${parsed} useEffect blocks scanned, `
  + `${withCancelFlag} with a cancellation flag, `
  + `${unparsed} concise-body effect(s) not parseable and out of scope).`);
