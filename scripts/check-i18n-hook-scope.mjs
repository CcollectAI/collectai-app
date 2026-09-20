#!/usr/bin/env node
/**
 * Every t(...) must sit inside a component that declares `t`.
 *
 * WHY: docs/I18N_BACKLOG.md step 2 says to confirm this by hand, and step 6
 * used to claim `check_i18n_defaults` enforced it. It does not — that script
 * matches one regex for t('key', { defaultValue }) and compares the English
 * against en.json. Nothing checked SCOPE, and `react-hooks/rules-of-hooks` is
 * not in eslint.config.js either, so the only thing standing between a
 * hook-less `t(` and production was tsc noticing an undefined name.
 *
 * ⚠️ CORRECTED 2026-09-20 — THIS GATE IS LARGELY REDUNDANT, and the premise it
 * was written on was wrong. I grepped `eslint.config.js` for the string
 * "react-hooks", found nothing, and concluded the rule was not enforced. It is:
 * the plugin arrives through a preset, and `react-hooks/rules-of-hooks` fires
 * as an ERROR. Measured against a two-component file where only one declares
 * `t`:
 *
 *     tsc               error TS2304: Cannot find name 't'   <- catches it
 *     rules-of-hooks    silent                               <- different class
 *     this gate         catches it
 *
 * So tsc is the real defence for an undeclared `t`, and rules-of-hooks covers
 * the conditional-hook case this gate never looked at. What is left here is
 * narrow: a `t` that RESOLVES lexically but from the wrong scope (a module-level
 * binding, or one captured from an enclosing closure), which compiles and is
 * not a hook-order violation. Kept because it is cheap and that case is real,
 * but it should not be cited as the thing standing between a hook-less `t` and
 * production. tsc is.
 *
 * This walks each top-level component and asserts that any t( inside it is
 * covered by a `const { t } = useTranslation()` in that same component.
 *
 *   node scripts/check-i18n-hook-scope.mjs      # exit 0 clean, 1 on findings
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const ROOTS = ['app', 'src'];
const DECL = /^(?:export\s+)?(?:default\s+)?(?:(?:const|function)\s+([A-Z]\w*)|const\s+([A-Z]\w*)\s*[:=]|export\s+default\s+React\.memo\(function\s+([A-Z]\w*))/;
const MEMO = /^export\s+default\s+React\.memo\(function\s+([A-Z]\w*)/;
const HAS_T = /const\s*\{[^}]*\bt\b[^}]*\}\s*=\s*useTranslation\(/;
const CALL = /(?<![\w.])t\(\s*['"][a-z][A-Za-z0-9_.]*['"]/;

function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    if (e === 'node_modules' || e === '__tests__') continue;
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (p.endsWith('.tsx')) out.push(p);
  }
  return out;
}

const problems = [];
let components = 0;
for (const file of ROOTS.flatMap((r) => walk(r))) {
  const lines = readFileSync(file, 'utf8').split('\n');
  const starts = [];
  lines.forEach((l, i) => { if (MEMO.test(l) || DECL.test(l)) starts.push(i); });
  for (let s = 0; s < starts.length; s++) {
    const from = starts[s];
    const to = s + 1 < starts.length ? starts[s + 1] : lines.length;
    const body = lines.slice(from, to);
    const uses = body.some((l) => CALL.test(l));
    if (!uses) continue;
    components++;
    if (!body.some((l) => HAS_T.test(l))) {
      const name = (lines[from].match(/(?:function|const)\s+([A-Z]\w*)/) || [])[1] || '?';
      const hit = from + body.findIndex((l) => CALL.test(l)) + 1;
      problems.push(`  ${file}:${hit}  ${name}() calls t() but never declares it`);
    }
  }
}

console.log(`checked ${components} component(s) that call t()`);
if (problems.length) {
  console.log(`\nFAIL  ${problems.length} component(s) use t() with no useTranslation() in scope:\n`);
  console.log(problems.join('\n'));
  console.log('\n      Add `const { t } = useTranslation();` as the FIRST statement of the\n' +
              '      component -- above any early return, or the hook becomes conditional.');
  process.exit(1);
}
console.log('PASS  every t() call sits in a component that declares t');
