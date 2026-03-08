#!/usr/bin/env node
/**
 * Bundle size monitoring script.
 *
 * Exports the JS bundle, measures its size, compares to the
 * baseline in .bundle-baseline.json, and warns if growth > 5%.
 *
 * Usage:
 *   node scripts/bundle-size.mjs          # Check against baseline
 *   node scripts/bundle-size.mjs --update # Generate/update baseline
 */

import { execSync } from 'child_process';
import { readFileSync, writeFileSync, statSync, existsSync, unlinkSync, rmSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const BASELINE_PATH = resolve(ROOT, '.bundle-baseline.json');
const BUNDLE_OUTPUT = resolve(ROOT, '.tmp-bundle-check.js');
const THRESHOLD = 0.05; // 5% growth threshold

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function exportBundle() {
  console.log('Exporting JS bundle...');
  try {
    execSync(
      `npx react-native bundle --platform ios --dev false --entry-file node_modules/expo-router/entry.js --bundle-output ${BUNDLE_OUTPUT} --minify false`,
      { cwd: ROOT, stdio: 'pipe', timeout: 120_000 },
    );
  } catch (err) {
    // Fallback: try metro directly
    try {
      execSync(
        `npx expo export --platform ios --output-dir .tmp-export-check`,
        { cwd: ROOT, stdio: 'pipe', timeout: 120_000 },
      );
      // Find the largest .js file in the export
      const exportDir = resolve(ROOT, '.tmp-export-check');
      if (existsSync(exportDir)) {
        rmSync(exportDir, { recursive: true, force: true });
      }
    } catch {
      // ignore fallback failure
    }
    console.error('Bundle export failed. Ensure metro/react-native CLI is available.');
    process.exit(1);
  }

  if (!existsSync(BUNDLE_OUTPUT)) {
    console.error('Bundle output file not found after export.');
    process.exit(1);
  }
  const stat = statSync(BUNDLE_OUTPUT);
  // Clean up
  try { unlinkSync(BUNDLE_OUTPUT); } catch {}
  // Also clean up source map if generated
  try { unlinkSync(BUNDLE_OUTPUT + '.map'); } catch {}

  return stat.size;
}

function readBaseline() {
  if (!existsSync(BASELINE_PATH)) return null;
  const raw = readFileSync(BASELINE_PATH, 'utf-8');
  return JSON.parse(raw);
}

function writeBaseline(size) {
  const data = {
    sizeBytes: size,
    sizeHuman: formatBytes(size),
    date: new Date().toISOString(),
  };
  writeFileSync(BASELINE_PATH, JSON.stringify(data, null, 2) + '\n');
  console.log(`Baseline updated: ${data.sizeHuman}`);
}

// Main
const isUpdate = process.argv.includes('--update');
const currentSize = exportBundle();

console.log(`Current bundle size: ${formatBytes(currentSize)}`);

if (isUpdate) {
  writeBaseline(currentSize);
  process.exit(0);
}

const baseline = readBaseline();
if (!baseline) {
  console.log('No baseline found. Run with --update to create one.');
  writeBaseline(currentSize);
  process.exit(0);
}

const growth = (currentSize - baseline.sizeBytes) / baseline.sizeBytes;
const growthPct = (growth * 100).toFixed(1);

console.log(`Baseline: ${baseline.sizeHuman} (${baseline.date})`);
console.log(`Change: ${growth >= 0 ? '+' : ''}${growthPct}%`);

if (growth > THRESHOLD) {
  console.error(`\nBundle size grew by ${growthPct}% (threshold: ${(THRESHOLD * 100).toFixed(0)}%)`);
  console.error('Review recent changes for unnecessary dependencies or code.');
  process.exit(1);
} else {
  console.log('Bundle size within acceptable range.');
  process.exit(0);
}
