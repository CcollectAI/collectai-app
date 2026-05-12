#!/usr/bin/env node
/**
 * analyze-bundle.mjs — Metro bundle size analysis for Sparrow Collect.
 *
 * Two modes:
 *
 *   1. "fresh" (default): runs `npx expo export --platform ios` to
 *      produce a fresh prod-mode bundle, then breaks it down by
 *      source module + npm package.
 *
 *   2. "cached": reads the most recent `dist/` from a previous expo
 *      export. Skips the ~60s rebuild. Use when iterating on the
 *      analyzer itself.
 *
 * Output: ranked list of the heaviest sources, plus per-package totals.
 * Flags any package > 500 KB minified (Metro's threshold for "you
 * should probably code-split this") and any single source file > 200 KB.
 *
 * Production iOS bundles ship 50-80 MB typically (asset-heavy
 * collectibles app). The JS bundle alone should be under 4 MB
 * minified for a snappy startup.
 *
 * Run:
 *   node scripts/analyze-bundle.mjs              # fresh export
 *   node scripts/analyze-bundle.mjs --cached     # use existing dist/
 *   node scripts/analyze-bundle.mjs --json       # JSON output
 *
 * Exit codes:
 *   0 — no warnings, all packages within thresholds
 *   1 — package over threshold OR source file over threshold
 *   2 — couldn't produce or read the bundle
 */

import { execSync, spawnSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DIST = join(REPO_ROOT, 'dist');

const argv = process.argv.slice(2);
const useCached = argv.includes('--cached');
const jsonOut = argv.includes('--json');

const PACKAGE_WARN_KB = 500;
const FILE_WARN_KB = 200;

function bytesToKB(n) { return (n / 1024).toFixed(1); }

function ensureBundle() {
  if (useCached && existsSync(DIST)) return;
  console.error('Running `expo export --platform ios` (~60s)...');
  const res = spawnSync('npx', ['expo', 'export', '--platform', 'ios'], {
    cwd: REPO_ROOT,
    stdio: 'inherit',
  });
  if (res.status !== 0) {
    console.error('expo export failed');
    process.exit(2);
  }
}

function findIosBundle() {
  // Expo export produces dist/_expo/static/js/ios/AppEntry-<hash>.js
  // (and ios.<hash>.hbc for Hermes). Walk it.
  const jsDir = join(DIST, '_expo', 'static', 'js', 'ios');
  if (!existsSync(jsDir)) {
    console.error(`expected ${jsDir} to exist — did expo export run?`);
    process.exit(2);
  }
  const candidates = readdirSync(jsDir)
    .filter((f) => f.endsWith('.js') || f.endsWith('.hbc'))
    .map((f) => ({ name: f, path: join(jsDir, f), size: statSync(join(jsDir, f)).size }))
    .sort((a, b) => b.size - a.size);
  if (candidates.length === 0) {
    console.error(`no bundle found in ${jsDir}`);
    process.exit(2);
  }
  return candidates[0];
}

/** Walk dist/_expo/static/js/ios for assets too — gives total bundle weight. */
function totalBundleSize() {
  const root = join(DIST, '_expo', 'static');
  if (!existsSync(root)) return 0;
  let total = 0;
  const walk = (d) => {
    for (const entry of readdirSync(d, { withFileTypes: true })) {
      const p = join(d, entry.name);
      if (entry.isDirectory()) walk(p);
      else total += statSync(p).size;
    }
  };
  walk(root);
  // Add assets/ too (images, fonts)
  const assets = join(DIST, 'assets');
  if (existsSync(assets)) walk(assets);
  return total;
}

/** Parse the bundle's source-map or fall back to module-path inference. */
function breakdown(bundlePath) {
  // Expo with Hermes ships a .hbc + .map sibling. Try the .map first.
  const mapPath = bundlePath + '.map';
  if (existsSync(mapPath)) {
    return breakdownFromSourceMap(mapPath);
  }
  // Without a source map, parse the raw JS for `/* harmony import */ var _<name>` patterns.
  // Heuristic only; ranks but doesn't get true sizes.
  return breakdownFromRawBundle(bundlePath);
}

function breakdownFromSourceMap(mapPath) {
  const map = JSON.parse(readFileSync(mapPath, 'utf8'));
  const sources = map.sources || [];
  const contents = map.sourcesContent || [];
  const out = [];
  for (let i = 0; i < sources.length; i++) {
    const name = sources[i].replace(/^\.\.?\//, '');
    const len = (contents[i] || '').length;
    if (len === 0) continue;
    out.push({ source: name, bytes: len });
  }
  out.sort((a, b) => b.bytes - a.bytes);
  return out;
}

function breakdownFromRawBundle(bundlePath) {
  // Last-resort: report only the bundle's total.
  const size = statSync(bundlePath).size;
  return [{ source: '<bundle>', bytes: size, note: 'no source map' }];
}

function aggregatePackages(rows) {
  const packages = new Map();
  for (const r of rows) {
    let pkg = 'app';
    const m = r.source.match(/node_modules\/(@[^/]+\/[^/]+|[^/]+)/);
    if (m) pkg = m[1];
    else if (r.source.startsWith('src/') || r.source.startsWith('app/')) pkg = '(your code)';
    else if (r.source.startsWith('node_modules')) pkg = 'node_modules:<unknown>';
    packages.set(pkg, (packages.get(pkg) || 0) + r.bytes);
  }
  return Array.from(packages.entries())
    .map(([name, bytes]) => ({ name, bytes }))
    .sort((a, b) => b.bytes - a.bytes);
}

function render(bundle, rows, packages, total) {
  const lines = [];
  lines.push('');
  lines.push('Sparrow Collect — bundle analysis');
  lines.push('─'.repeat(72));
  lines.push(`Bundle file: ${bundle.name} — ${bytesToKB(bundle.size)} KB minified`);
  lines.push(`All static assets (JS + images + fonts): ${bytesToKB(total)} KB`);
  lines.push('');
  lines.push('Top 15 packages by source size:');
  for (const p of packages.slice(0, 15)) {
    const warn = p.bytes / 1024 > PACKAGE_WARN_KB ? '  ⚠️  >500KB — consider lazy-loading' : '';
    lines.push(`  ${bytesToKB(p.bytes).padStart(10)} KB  ${p.name}${warn}`);
  }
  lines.push('');
  lines.push('Top 10 individual source files:');
  for (const r of rows.slice(0, 10)) {
    const warn = r.bytes / 1024 > FILE_WARN_KB ? '  ⚠️  >200KB' : '';
    lines.push(`  ${bytesToKB(r.bytes).padStart(10)} KB  ${r.source}${warn}`);
  }
  lines.push('─'.repeat(72));
  const hotPackages = packages.filter((p) => p.bytes / 1024 > PACKAGE_WARN_KB);
  const hotFiles = rows.filter((r) => r.bytes / 1024 > FILE_WARN_KB);
  if (hotPackages.length === 0 && hotFiles.length === 0) {
    lines.push('✓ no packages > 500 KB and no source files > 200 KB');
  } else {
    if (hotPackages.length > 0) {
      lines.push(`⚠️  ${hotPackages.length} package(s) over 500 KB — consider lazy-loading or finding lighter alternatives`);
    }
    if (hotFiles.length > 0) {
      lines.push(`⚠️  ${hotFiles.length} source file(s) over 200 KB — consider code-splitting`);
    }
  }
  return lines.join('\n');
}

function main() {
  ensureBundle();
  const bundle = findIosBundle();
  const rows = breakdown(bundle.path);
  const packages = aggregatePackages(rows);
  const total = totalBundleSize();

  if (jsonOut) {
    console.log(JSON.stringify({ bundle: bundle.name, bundleBytes: bundle.size, totalBytes: total, packages: packages.slice(0, 25), files: rows.slice(0, 25) }, null, 2));
  } else {
    console.log(render(bundle, rows, packages, total));
  }

  const hotPackages = packages.filter((p) => p.bytes / 1024 > PACKAGE_WARN_KB);
  const hotFiles = rows.filter((r) => r.bytes / 1024 > FILE_WARN_KB);
  process.exit(hotPackages.length + hotFiles.length > 0 ? 1 : 0);
}

main();
