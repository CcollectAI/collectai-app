#!/usr/bin/env node
/**
 * The action half-happened, and only the log says so.
 *
 * `create-event.tsx` created the event, then saved it as a template inside its
 * own try/catch that logged and carried on, then navigated back. A member who
 * ticked "save as template" left believing they had one (class sweep K,
 * 2026-09-17).
 *
 * `check-silent-failures --strict` passed that code **before and after the
 * fix**, because rule B asks "was it logged?" — the same wrong question that
 * let 74 empty-on-failure sites through until rule F was written. Logging is
 * what the developer finds out. This asks what the MEMBER finds out.
 *
 * The shape: a catch whose body does NOTHING BUT LOG, inside a function that
 * had already awaited something before the try. The earlier await is what makes
 * it different from an ordinary swallow — the action's primary effect already
 * landed, so continuing silently leaves the member believing all of it did.
 *
 * "Nothing but log" is the discriminator, and it is what separates the two
 * versions of the worked instance:
 *
 *     catch (tplErr) { logger.error(…); }                    ← reported
 *     catch (tplErr) { templateSaved = false; logger.error(…); }  ← not
 *
 * The second is the fix: the flag is read after the try and drives a toast that
 * names what did not happen. Any statement other than a log — a flag, a toast,
 * a return, a rethrow — means something downstream can still tell, so it is out
 * of scope here and rule B keeps it.
 *
 * Exempt a genuine best-effort failure with the marker rule B already uses:
 *     // best-effort: analytics ping, nothing the member is waiting on
 *
 * Known blind spot: the enclosing function is found by walking out to a `=>` or
 * a `function …()` opener, so a catch inside an object/class METHOD shorthand
 * (`foo() {`) is skipped rather than guessed at. Every handler in this codebase
 * is an arrow function.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const SCAN = ['app', 'src'];

const walk = (dir, out = []) => {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e === '__tests__' || e.startsWith('.')) continue;
    const f = join(dir, e);
    if (statSync(f).isDirectory()) walk(f, out);
    else if (/\.(ts|tsx)$/.test(e)) out.push(f);
  }
  return out;
};

export function scan(src) {
  const out = [];
  const lineOf = (i) => src.slice(0, i).split('\n').length;

  for (const m of src.matchAll(/catch\s*(?:\([^)]*\))?\s*\{/g)) {
    const ls = src.lastIndexOf('\n', m.index) + 1;
    const head0 = src.slice(ls, m.index);
    if (head0.includes('//') || /^\s*\*/.test(head0) || /^\s*\/\*/.test(head0)) continue;

    let depth = 0, i = m.index + m[0].length - 1, end = -1;
    for (; i < src.length; i++) {
      if (src[i] === '{') depth++;
      else if (src[i] === '}') { depth--; if (depth === 0) { end = i; break; } }
    }
    if (end === -1) continue;
    const raw = src.slice(m.index + m[0].length, end);
    if (raw.length > 4000) continue;
    // Honour the markers this codebase already uses for a written decision.
    // `empty-ok:` belongs to rule F, and `useValueSummary` carried one before
    // this rule existed — re-reporting a site whose reason is already written
    // is how a gate trains people to ignore it.
    if (/best-effort:|empty-ok:/.test(raw)) continue;

    const stmts = raw
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .split('\n').map((l) => l.replace(/\/\/.*$/, '').trim()).filter(Boolean)
      .flatMap((l) => l.split(';')).map((s) => s.trim()).filter(Boolean);
    if (stmts.length === 0) continue;               // empty catch — rule B owns it

    // Every statement must be part of a log call. A log may span lines, so
    // once one opens, continuation fragments count until its closing paren.
    let logOnly = true, inLog = false;
    for (const s of stmts) {
      if (!inLog && /^(logger|console|Sentry)\./.test(s)) { inLog = !/\)\s*$/.test(s); continue; }
      if (inLog) { if (/\)\s*$/.test(s)) inLog = false; continue; }
      logOnly = false; break;
    }
    if (!logOnly) continue;

    const tryIdx = src.lastIndexOf('try', m.index);
    if (tryIdx === -1) continue;

    // Walk out to the enclosing FUNCTION. Matching `)` alone read
    // `if (saveAsTemplate && templateName.trim())` as a function opener, which
    // stopped the walk at the `if` and hid the primary write above it.
    let from = tryIdx, fnOpen = -1;
    for (let hop = 0; hop < 10; hop++) {
      let d = 0, j = from, open = -1;
      for (; j >= 0; j--) {
        if (src[j] === '}') d++;
        else if (src[j] === '{') { if (d === 0) { open = j; break; } d--; }
      }
      if (open === -1) break;
      const head = src.slice(Math.max(0, open - 160), open);
      if (/=>\s*$/.test(head) || /\bfunction\b[^{]*\)\s*$/.test(head)) { fnOpen = open; break; }
      from = open - 1;
    }
    if (fnOpen === -1) continue;

    // A prior WRITE, not merely a prior await. "Something already happened"
    // is the whole premise, and the first version asked only for `await`,
    // which made three shapes look like the bug and none of them was:
    //   - a prior READ that degrades on purpose (`item/[id].tsx` falls back to
    //     the row's own columns, and says so);
    //   - ENRICHMENT before the primary write (`add-manual.tsx` matches the
    //     catalog first, then inserts — nothing had happened yet);
    //   - a read whose catch already carried an `empty-ok:` reason.
    const before = src.slice(fnOpen, tryIdx);
    const WRITE = /\bawait\s+[\w.]*\b(create|insert|update|upsert|delete|remove|save|upload|mutate|submit|patch|post)[A-Z_(]/;
    if (!WRITE.test(before)) continue;

    out.push({ line: lineOf(m.index), snippet: stmts[0].slice(0, 80) });
  }
  return out;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const findings = [];
  for (const abs of SCAN.flatMap((d) => walk(join(ROOT, d)))) {
    const rel = relative(ROOT, abs);
    for (const f of scan(readFileSync(abs, 'utf8'))) findings.push({ at: `${rel}:${f.line}`, ...f });
  }
  if (findings.length) {
    console.error(`✗ half-done silence — ${findings.length} catch(es) that only log, after the action already wrote something:`);
    for (const f of findings) {
      console.error(`   ${f.at}`);
      console.error(`      ${f.snippet}`);
    }
    console.error('\n   The member cannot tell the second half failed. Set a flag the caller reads');
    console.error('   and say what did not happen, or add "// best-effort: <why nobody is waiting on it>".');
    process.exit(1);
  }
  console.log('✓ half-done silence — no action fails its second half with only a log.');
}
