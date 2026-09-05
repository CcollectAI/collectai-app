#!/usr/bin/env node
/**
 * Find catch blocks that swallow the outcome of a USER-INITIATED action.
 *
 * The defect this generalises (app/(auth)/verify-email.tsx, found 2026-09-05):
 *
 *     const { error } = await supabase.auth.resend({ type: 'signup', email });
 *     if (error) throw error;
 *     setResent(true);
 *     setCooldown(60);
 *   } catch {
 *     // account-enumeration defence
 *   }
 *
 * A 429 threw, so `setResent` and `setCooldown` never ran: the user tapped
 * "Resend email" and NOTHING happened — no confirmation, no error, no
 * countdown. Silence on the one screen whose job is "your email is coming".
 *
 * The tell is not "an empty catch" — plenty of those are correct (a polling
 * tick, a haptic, an analytics call). It is an empty catch on a handler that
 * (a) is invoked from a press handler, and (b) sets state in the try block
 * which the catch then leaves stale.
 *
 * Exit 1 if any unreviewed finding remains. Reviewed-and-intentional cases go
 * in scripts/silent-catch-allowlist.txt with a reason, same convention as
 * scripts/router_drift_allowlist.txt.
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = process.cwd();
const SCAN = ['app', 'src', 'components'];
const ALLOWLIST = join(ROOT, 'scripts', 'silent-catch-allowlist.txt');

const allow = new Set(
  existsSync(ALLOWLIST)
    ? readFileSync(ALLOWLIST, 'utf8')
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => l && !l.startsWith('#'))
    : [],
);

function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e.startsWith('.')) continue;
    const p = join(dir, e);
    const st = statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (/\.(ts|tsx)$/.test(e) && !/\.(test|spec)\./.test(e)) out.push(p);
  }
  return out;
}

const findings = [];

for (const file of SCAN.flatMap((d) => (existsSync(join(ROOT, d)) ? walk(join(ROOT, d)) : []))) {
  const raw = readFileSync(file, 'utf8');
  const rel = relative(ROOT, file);
  const lines = raw.split('\n');

  // Blank out comments and string literals BEFORE looking for `catch`, keeping
  // offsets identical so line numbers still line up. Without this the checker
  // matched the words "a bare `catch {}`" inside a comment that was DESCRIBING
  // the bug, and reported the fixed file as broken. A checker that cannot tell
  // code from prose about code is worse than none.
  const src = raw
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
    .replace(/\/\/[^\n]*/g, (m) => ' '.repeat(m.length))
    .replace(/`(?:\\.|[^`\\])*`/g, (m) => m.replace(/[^\n]/g, ' '))
    .replace(/'(?:\\.|[^'\\\n])*'/g, (m) => ' '.repeat(m.length))
    .replace(/"(?:\\.|[^"\\\n])*"/g, (m) => ' '.repeat(m.length));

  // Every `catch {` / `catch (e) {` whose body has no statement (comments only).
  const re = /catch\s*(\([^)]*\))?\s*\{/g;
  let m;
  while ((m = re.exec(src)) !== null) {
    // Walk to the matching close brace.
    let depth = 1;
    let i = re.lastIndex;
    while (i < src.length && depth > 0) {
      if (src[i] === '{') depth++;
      else if (src[i] === '}') depth--;
      i++;
    }
    const body = src.slice(re.lastIndex, i - 1);
    const stripped = body
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/\/\/[^\n]*/g, '')
      .trim();
    if (stripped) continue; // it does something — not silent

    const line = src.slice(0, m.index).split('\n').length;

    // The enclosing function, walking backwards to the nearest declaration.
    let fnName = '(unknown)';
    for (let l = line - 1; l >= 0 && l > line - 120; l--) {
      const fm = /(?:async\s+)?function\s+([A-Za-z0-9_]+)|const\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\(/.exec(
        lines[l] ?? '',
      );
      if (fm) { fnName = fm[1] || fm[2]; break; }
    }

    // Find the EXACT try block this catch belongs to, by matching braces
    // backwards from the `}` that precedes `catch`. A fixed 40-line lookback
    // read back past the enclosing function and credited an unrelated
    // handler's setters to a background poll's catch — the checker's own
    // version of the bug it hunts: attributing an effect to the wrong cause.
    let j = m.index - 1;
    while (j >= 0 && /\s/.test(src[j])) j--;
    let tryBlock = '';
    if (src[j] === '}') {
      let d = 1;
      let k = j - 1;
      while (k >= 0 && d > 0) {
        if (src[k] === '}') d++;
        else if (src[k] === '{') d--;
        k--;
      }
      const before = src.slice(Math.max(0, k - 6), k + 1);
      if (/\btry\s*$/.test(before)) tryBlock = src.slice(k + 2, j);
    }
    if (!tryBlock) continue; // not a try/catch we can attribute — say nothing
    // setInterval/setTimeout are not React state — counting them made the
    // background verification poll (correctly silent) look like a swallowed
    // user action.
    const TIMERS = new Set(['setInterval', 'setTimeout', 'setImmediate']);
    const setters = [...tryBlock.matchAll(/\bset([A-Z][A-Za-z0-9_]*)\s*\(/g)]
      .map((x) => 'set' + x[1])
      .filter((n) => !TIMERS.has(n));

    // Is this handler wired to a press/submit? (user-initiated)
    const wired =
      new RegExp(`onPress=\\{${fnName}\\}|onPress=\\{\\(\\)\\s*=>\\s*${fnName}|onSubmit=\\{${fnName}\\}`).test(src);

    if (setters.length && wired) {
      const key = `${rel}:${fnName}`;
      if (allow.has(key)) continue;
      findings.push({ rel, line, fnName, setters: [...new Set(setters)] });
    }
  }
}

if (!findings.length) {
  console.log('SILENT-CATCH AUDIT: no user-initiated handler swallows its own outcome.');
  process.exit(0);
}

console.log(`SILENT-CATCH AUDIT: ${findings.length} finding(s)\n`);
for (const f of findings) {
  console.log(`  ${f.rel}:${f.line}  ${f.fnName}()`);
  console.log(`      press-wired, and the catch leaves these stale: ${f.setters.join(', ')}`);
}
console.log('\nEither surface the failure, or add "<file>:<fn>" to scripts/silent-catch-allowlist.txt with a reason.');
process.exit(1);
