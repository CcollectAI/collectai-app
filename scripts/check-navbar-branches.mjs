#!/usr/bin/env node
/**
 * A screen that shows the QuickNavBar must show it in EVERY return branch.
 *
 * docs/ui-playbook.md has said so since 2026-08-16 ("Cover every return
 * branch": a not-found branch without the bar stranded a deep link) and the
 * 2026-09-13 walk broke it again on Analytics and Public profile. Nothing
 * checked it. On 2026-09-15 the sponsor dashboard's loading, failed and empty
 * branches — and a brand-new failed branch added that day — had no bar, seen on
 * a device with the API down; enumerated, 19 returns in 10 screens.
 *
 * The check is AST-based, not a regex: a first grep counted returns inside
 * nested helper components and the ScreenErrorBoundary wrappers and reported 42
 * files. For each capitalised component that renders <QuickNavBar /> in at least
 * one JSX return, every other JSX return of THAT component (not of a function
 * nested in it) must render it too.
 *
 * Adding the bar is not enough on its own: it must follow a sibling that fills
 * (`flex: 1`), or it floats mid-screen — see "A nav bar below a margin-only
 * sibling floats" in the playbook. This gate checks presence, not placement.
 *
 * Exempt a return with `// navbar-ok: <reason>` on the line above `return (`.
 *
 * RULE 2 (2026-09-15): a screen that renders the bar in NO branch is invisible
 * to rule 1 — the sweep found catalogue item, catalogue set, listing detail and
 * the sell flow with no bar at all. Every route file must render <QuickNavBar />
 * unless it is in NO_NAVBAR_BY_DESIGN below, each entry with its reason (the
 * playbook's list from 2026-08-16, plus legal pages approved 2026-09-15).
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { createRequire } from 'node:module';

const ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const require = createRequire(join(ROOT, 'package.json'));
const { parse } = require('@babel/parser');
const traverse = require('@babel/traverse').default;

const walk = (dir, out = []) => {
  for (const e of readdirSync(dir)) {
    if (e.startsWith('.') || e === 'node_modules') continue;
    const f = join(dir, e);
    if (statSync(f).isDirectory()) walk(f, out);
    else if (e.endsWith('.tsx')) out.push(f);
  }
  return out;
};

const rendersNavBar = (path) => {
  let found = false;
  path.traverse({
    JSXOpeningElement(p) {
      if (p.node.name.name === 'QuickNavBar') { found = true; p.stop(); }
    },
  });
  return found;
};

const NO_NAVBAR_BY_DESIGN = [
  [/^\(auth\)\//, 'no navigation before login'],
  [/^\(tabs\)\//, 'tab screens have the real tab bar'],
  [/^(index|home\/portfolio|alerts|chat-demo|l\/\[id\])$/, 'redirect routes render no screen of their own'],
  [/^franchise\/\[id\]$/, 'redirects to the tabs while FRANCHISE_PAGES_ENABLED=false'],
  [/^(quickscan|barcode-scan)$/, 'full-bleed camera screens'],
  [/^chat\/new$/, 'chat compose (docs/ui-playbook.md 2026-08-16)'],
  [/^legal\//, 'opened from Register before an account exists — a bar would send a half-registered visitor into screens that need one (approved 2026-09-15)'],
  [/^diagnostics$/, 'developer log screen'],
  [/^import-url$/, 'not reachable in the app (URL import deferred)'],
  [/^sell\/ebay-defaults$/, 'renders SellingUnavailable while SELLING_ENABLED=false'],
];
const findings = [];
for (const abs of walk(join(ROOT, 'app'))) {
  const src = readFileSync(abs, 'utf8');
  const route = relative(join(ROOT, 'app'), abs).replace(/\.tsx$/, '');
  if (route.startsWith('_layout') || route.includes('/_layout') || route.startsWith('+')) continue;
  if (!src.includes('<QuickNavBar')) {
    if (!NO_NAVBAR_BY_DESIGN.some(([re]) => re.test(route))) {
      findings.push(`app/${route}.tsx  renders no <QuickNavBar /> in any branch (not in NO_NAVBAR_BY_DESIGN)`);
    }
    continue;
  }
  const lines = src.split('\n');
  const ast = parse(src, { sourceType: 'module', plugins: ['jsx', 'typescript'] });
  const byComponent = new Map();
  traverse(ast, {
    ReturnStatement(p) {
      const arg = p.get('argument');
      if (!arg.node || !(arg.isJSXElement() || arg.isJSXFragment())) return;
      const fn = p.getFunctionParent();
      if (!fn) return;
      let name = fn.node.id?.name;
      if (!name && fn.parentPath.isVariableDeclarator()) name = fn.parentPath.node.id.name;
      if (!name || !/^[A-Z]/.test(name)) return;
      const line = p.node.loc.start.line;
      if (/navbar-ok:/.test(lines[line - 2] ?? '')) return;
      if (!byComponent.has(fn.node)) byComponent.set(fn.node, { name, returns: [] });
      byComponent.get(fn.node).returns.push({ line, nav: rendersNavBar(arg) });
    },
  });
  for (const { name, returns } of byComponent.values()) {
    if (!returns.some((r) => r.nav)) continue;
    for (const r of returns.filter((x) => !x.nav)) {
      findings.push(`${relative(ROOT, abs)}:${r.line}  ${name} returns without <QuickNavBar /> (another branch of it has one)`);
    }
  }
}

if (findings.length) {
  console.error(`✗ navbar branches — ${findings.length} return branch(es) drop the nav bar:`);
  for (const f of findings) console.error(`   ${f}`);
  process.exit(1);
}
console.log('✓ navbar branches — every screen renders QuickNavBar in every return branch (or is exempt by design, with a reason).');
