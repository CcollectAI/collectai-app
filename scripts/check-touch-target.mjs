#!/usr/bin/env node
/**
 * A control smaller than 44pt needs `hitSlop`.
 *
 * Apple HIG asks for 44×44pt, Android for 48dp. This app draws plenty of 28-40pt
 * icon buttons — a send arrow, a calendar's month arrows, a row's ⋯ — and they
 * look right at that size. The fix is not to inflate the box (that re-lays out
 * the row); it is `hitSlop`, which grows the TOUCHABLE area and leaves the
 * drawing alone. The playbook already says so for a 32pt target around a 20pt
 * icon ("the touch target and hitSlop are unchanged").
 *
 * A finding is a pressable whose OWN style object declares a width or height
 * below 44, with no `hitSlop` and no padding to make up the difference.
 *
 * ⚠️ hitSlop overlaps between NEIGHBOURS steal each other's edge: the topmost
 * hit rect wins, so a pair of arrows 6pt apart with 8pt of slop each makes the
 * boundary ambiguous. Extend the free sides fully and the shared side by at most
 * half the gap — that is why the fixes here are directional objects rather than
 * `hitSlop={8}`.
 *
 * Exempt with a reason in the comment block above the control:
 *     // touch-ok: <why this one cannot grow>          (in code)
 *     {/* touch-ok: <why this one cannot grow> *_/}     (in JSX)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const STRICT = process.argv.includes('--strict');
const MIN = 44;

const walk = (dir, out = []) => {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e === '__tests__' || e.startsWith('.')) continue;
    const f = join(dir, e);
    if (statSync(f).isDirectory()) walk(f, out);
    else if (/\.tsx$/.test(e)) out.push(f);
  }
  return out;
};
const lineOf = (s, i) => s.slice(0, i).split('\n').length;
const PRESS = /<(AnimatedPressable|Pressable|TouchableOpacity|TouchableHighlight)\b/g;

/** End of the opening tag, ignoring `>` inside a `{…}` expression. */
function openTagEnd(s, i) {
  let depth = 0;
  for (let j = i; j < s.length; j++) {
    if (s[j] === '{') depth++;
    else if (s[j] === '}') depth--;
    else if (s[j] === '>' && depth === 0) return j;
  }
  return -1;
}

const findings = [];
for (const abs of ['app', 'src'].flatMap((d) => walk(join(ROOT, d)))) {
  const rel = relative(ROOT, abs);
  if (/\/mocks?\//.test(rel)) continue;
  const src = readFileSync(abs, 'utf8');

  // Every `name: { … }` in the file's StyleSheet — one level of nesting only,
  // which is what a style object is.
  const styles = {};
  for (const m of src.matchAll(/(\w+)\s*:\s*\{([^{}]*)\}/g)) styles[m[1]] = m[2];

  for (const m of src.matchAll(PRESS)) {
    const end = openTagEnd(src, m.index);
    if (end < 0) continue;
    const tag = src.slice(m.index, end + 1);
    if (/hitSlop/.test(tag)) continue;
    const ref = tag.match(/style=\{(?:\[)?\s*styles\.(\w+)/);
    if (!ref || !styles[ref[1]]) continue;
    const decl = styles[ref[1]];
    if (/padding/.test(decl)) continue;           // padding grows the box itself
    const w = decl.match(/\bwidth:\s*(\d+)/);
    const h = decl.match(/\bheight:\s*(\d+)/);
    const small = (w && +w[1] < MIN) || (h && +h[1] < MIN);
    if (!small) continue;
    // the reason, from the contiguous comment block above the pressable
    const lines = src.slice(0, m.index).split('\n');
    let reason = '';
    for (let k = lines.length - 2; k >= 0; k--) {
      const t = lines[k].trim();
      if (t === '') { if (reason) break; continue; }
      // `{/* … */}` too: in JSX child position a `//` comment is a syntax error,
      // so the marker this gate ASKS for could not be written at most of these
      // sites. A gate must accept the spelling its own message demands.
      if (!t.startsWith('//') && !t.startsWith('*') && !t.startsWith('/*') && !t.startsWith('{/*')) break;
      reason = t + '\n' + reason;
    }
    if (/touch-ok:/.test(reason) || /touch-ok:/.test(tag)) continue;
    findings.push(`${rel}:${lineOf(src, m.index)}  styles.${ref[1]} (w=${w ? w[1] : '-'} h=${h ? h[1] : '-'})`);
  }
}

if (findings.length) {
  console.error(`✗ touch target — ${findings.length} control(s) under ${MIN}pt with no hitSlop:`);
  for (const f of findings) console.error(`   ${f}`);
  console.error('\n   Add hitSlop — directional where a neighbour is close:');
  console.error('     hitSlop={{ top: 8, bottom: 8, left: 4, right: 4 }}');
  console.error('   or a reason above the control — `// touch-ok: <why>` in code,');
  console.error('   `{/* touch-ok: <why> */}` in JSX.');
  if (STRICT) process.exit(1);
  process.exit(0);
}
console.log(`✓ touch target — every control under ${MIN}pt extends its touch area, or says why not.`);
