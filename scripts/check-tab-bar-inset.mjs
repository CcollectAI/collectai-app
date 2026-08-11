#!/usr/bin/env node
/**
 * check-tab-bar-inset — every vertical scroller on a `(tabs)` screen must
 * reserve space for the tab bar.
 *
 * WHY THIS EXISTS
 *
 * `src/components/ExternalTabBar.tsx` is rendered at the ROOT stack, outside
 * the <Tabs> navigator (the navigator's own bar dropped touches in production
 * — see memory/project_tab_bar_bug_saga.md). It is `position: 'absolute';
 * bottom: 0` with height `EXTERNAL_TAB_BAR_HEIGHT (58) + max(insets.bottom,
 * 10)` — 68pt on a flat-bottom device, ~92pt on a notched one — and **nothing
 * reserves layout space for it**.
 *
 * So every `(tabs)` screen has to pad its own scroll content, and a hand-picked
 * number is always the wrong number: it is right on the phone it was eyeballed
 * on and short everywhere else. Measured 2026-08-05, five of six screens were
 * clipping their last row. The symptom is nasty because it looks like nothing:
 * the last card is VISIBLE, just with its bottom under the bar, and it is worst
 * in a filtered view that is too short to scroll further to compensate.
 *
 * THE RULE
 *
 * A vertical scroller on a `(tabs)` screen passes if its `contentContainerStyle`
 * references an inset variable (`useTabBarInset()` — see
 * src/hooks/useTabBarInset.ts, which derives the number from the bar instead of
 * guessing it). A literal `paddingBottom` passes only if it is already >= the
 * notched worst case; anything smaller is the bug this gate exists to catch.
 *
 * Horizontal rails are skipped — the bar is not over their scroll axis.
 *
 * ESCAPE HATCH
 *
 * A scroller that genuinely does not sit under the bar (it is inside a modal
 * that covers it, or the screen is not reachable as a tab) can carry
 *
 *     // tab-bar-inset-ok: <reason>
 *
 * on the line above the opening tag. The reason is required — a bare marker
 * does not suppress.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const TABS_DIR = 'app/(tabs)';
// EXTERNAL_TAB_BAR_HEIGHT (58) + a notched device's insets.bottom (~34).
// A literal at or above this clears the bar on every device we ship to.
const NOTCHED_WORST_CASE = 92;
const SCROLLERS = /<(Animated\.)?(ScrollView|FlatList|FlashList|SectionList|KeyboardAwareScrollView)\b/g;

/** Opening JSX tag starting at `from`, brace/quote aware so nested {{...}} survives. */
function readOpeningTag(src, from) {
  let depth = 0;
  let quote = null;
  for (let i = from; i < src.length; i++) {
    const c = src[i];
    if (quote) {
      if (c === quote && src[i - 1] !== '\\') quote = null;
      continue;
    }
    if (c === '"' || c === "'" || c === '`') { quote = c; continue; }
    if (c === '{') depth++;
    else if (c === '}') depth--;
    else if (c === '>' && depth === 0) return src.slice(from, i + 1);
  }
  return src.slice(from);
}

/** Value expression of `prop={...}` inside an opening tag. */
function propValue(tag, prop) {
  const at = tag.indexOf(`${prop}={`);
  if (at === -1) return null;
  let depth = 0;
  const start = at + prop.length + 1;
  for (let i = start; i < tag.length; i++) {
    if (tag[i] === '{') depth++;
    else if (tag[i] === '}') { depth--; if (depth === 0) return tag.slice(start + 1, i); }
  }
  return null;
}

/** paddingBottom declared on a StyleSheet key, e.g. `content: { paddingBottom: 80 }`. */
function styleKeyPaddingBottom(src, key) {
  const m = new RegExp(`\\b${key}\\s*:\\s*\\{`).exec(src);
  if (!m) return null;
  let depth = 0;
  for (let i = m.index + m[0].length - 1; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') {
      depth--;
      if (depth === 0) {
        const body = src.slice(m.index, i + 1);
        const pb = /paddingBottom\s*:\s*(\d+)/.exec(body);
        return pb ? Number(pb[1]) : null;
      }
    }
  }
  return null;
}

const failures = [];
const checked = [];

for (const file of readdirSync(TABS_DIR).filter((f) => f.endsWith('.tsx') && f !== '_layout.tsx')) {
  const path = join(TABS_DIR, file);
  const src = readFileSync(path, 'utf8');

  for (const match of [...src.matchAll(SCROLLERS)]) {
    const tag = readOpeningTag(src, match.index);
    const line = src.slice(0, match.index).split('\n').length;
    const name = `${match[1] ?? ''}${match[2]}`;

    // Not scrollers under the bar: a horizontal rail (the bar is not on its
    // scroll axis) and a `scrollEnabled={false}` grid (it is a layout container
    // nested inside a real scroller, which owns the padding).
    if (/\bhorizontal\b/.test(tag)) continue;
    if (/scrollEnabled=\{false\}/.test(tag)) continue;

    // Lookback has to clear a wrapped multi-line marker: the last entry of the
    // split is the indentation before `<Tag`, so a 3-line window only reaches
    // the marker when it fits on one line, and silently ignored it otherwise.
    const before = src.slice(0, match.index).split('\n').slice(-6).join('\n');
    const ok = /tab-bar-inset-ok:\s*\S+/.exec(before);
    if (ok) { checked.push(`${path}:${line} ${name} — allowed (${ok[0].split(':').slice(1).join(':').trim()})`); continue; }

    const ccs = propValue(tag, 'contentContainerStyle');
    if (ccs === null) {
      failures.push({ path, line, name, why: 'no contentContainerStyle at all — content ends flush against the bar' });
      continue;
    }
    if (/[Ii]nset/.test(ccs)) { checked.push(`${path}:${line} ${name} — uses inset`); continue; }

    // Largest paddingBottom reachable from this contentContainerStyle: an
    // inline literal, or one declared on any styles.* key it references.
    const literals = [...ccs.matchAll(/paddingBottom\s*:\s*(\d+)/g)].map((m) => Number(m[1]));
    for (const ref of ccs.matchAll(/styles\.(\w+)/g)) {
      const pb = styleKeyPaddingBottom(src, ref[1]);
      if (pb !== null) literals.push(pb);
    }
    const effective = literals.length ? Math.max(...literals) : 0;

    if (effective >= NOTCHED_WORST_CASE) {
      checked.push(`${path}:${line} ${name} — literal ${effective} clears ${NOTCHED_WORST_CASE}`);
    } else {
      failures.push({
        path, line, name,
        why: `paddingBottom ${effective} < ${NOTCHED_WORST_CASE} — clips the last row by ${NOTCHED_WORST_CASE - effective}pt on a notched device`,
      });
    }
  }
}

if (failures.length) {
  console.error(`\n✗ tab-bar-inset — ${failures.length} scroller(s) do not clear ExternalTabBar:\n`);
  for (const f of failures) console.error(`  ${f.path}:${f.line}  <${f.name}>\n      ${f.why}`);
  console.error(`\n  Fix: import { useTabBarInset } from '@/hooks/useTabBarInset', then`);
  console.error(`  contentContainerStyle={[styles.x, { paddingBottom: bottomInset }]}.`);
  console.error(`  See app/(tabs)/events.tsx for the pattern.\n`);
  process.exit(1);
}

console.log(`✓ tab-bar-inset — all ${checked.length} vertical scroller(s) on (tabs) screens clear the bar.`);
