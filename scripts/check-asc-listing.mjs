#!/usr/bin/env node
/**
 * check-asc-listing.mjs — validate App Store Connect listing copy
 * against Apple's hard length limits BEFORE pasting into ASC.
 *
 * Reads `docs/app-store-aso.md`, parses the iOS App Store Connect
 * section, and asserts each field is within its character cap. Same
 * checker logic for Google Play (similar caps, different keywords
 * field semantics — Apple uses comma-separated, Play uses a single
 * string).
 *
 * Apple's caps as of 2024:
 *   App Name              30 chars
 *   Subtitle              30 chars
 *   Keywords              100 chars (commas count)
 *   Promotional Text      170 chars
 *   Description           4000 chars
 *   What's New            4000 chars
 *
 * Run from repo root:
 *   node scripts/check-asc-listing.mjs
 *
 * Exit codes:
 *   0 — all fields within limits
 *   1 — one or more fields over limit, OR a field is missing entirely
 *   2 — couldn't read the source file
 *
 * Wire into CI as a step in `ci-min.yml` if you want pre-merge enforcement.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const ASO_PATH = join(REPO_ROOT, 'docs/app-store-aso.md');

const APPLE_LIMITS = {
  'App Name': 30,
  'Subtitle': 30,
  'Keywords': 100,
  'Promotional Text': 170,
  'Description': 4000,
  "What's New": 4000,
};

const PLAY_LIMITS = {
  'App Name': 30,
  'Short Description': 80,
  'Full Description': 4000,
};

/**
 * Parse a markdown file looking for `### <Field Name>` followed by an
 * indented code fence. Returns { fieldName: bodyText }.
 *
 * Stops scanning if it hits another `## ` (next major section).
 */
function parseListingSection(md, sectionName) {
  const lines = md.split('\n');
  const out = {};
  let currentField = null;
  let inFence = false;
  let inSection = false;
  let buffer = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith('## ')) {
      // New top-level section — stop if we just left ours
      if (inSection && !line.startsWith(`## ${sectionName}`)) break;
      inSection = line.includes(sectionName);
      continue;
    }
    if (!inSection) continue;

    const fieldMatch = line.match(/^###\s+([^(]+?)(?:\s*\([^)]*\))?\s*$/);
    if (fieldMatch) {
      if (currentField && buffer.length) out[currentField] = buffer.join('\n').trim();
      currentField = fieldMatch[1].trim();
      buffer = [];
      inFence = false;
      continue;
    }

    if (line.startsWith('```')) {
      inFence = !inFence;
      continue;
    }

    if (inFence && currentField) {
      buffer.push(line);
    }
  }
  if (currentField && buffer.length) out[currentField] = buffer.join('\n').trim();
  return out;
}

function checkLimits(label, fields, limits) {
  const findings = [];
  for (const [name, max] of Object.entries(limits)) {
    const value = fields[name];
    if (value == null) {
      findings.push({
        section: label, name, status: 'MISSING', length: 0, max,
        detail: `field "${name}" not found in the ${label} section`,
      });
      continue;
    }
    const len = value.length;
    const status =
      len === 0 ? 'EMPTY' :
      len > max ? 'OVER' :
      len > max * 0.95 ? 'NEAR_LIMIT' :
      'OK';
    findings.push({ section: label, name, status, length: len, max });
  }
  return findings;
}

function render(findings) {
  const colors = {
    OK: '\x1b[32m', NEAR_LIMIT: '\x1b[33m', OVER: '\x1b[31m',
    MISSING: '\x1b[31m', EMPTY: '\x1b[31m', RESET: '\x1b[0m',
  };
  const lines = ['', 'ASC + Play listing length audit', '─'.repeat(60)];
  for (const f of findings) {
    const c = colors[f.status] ?? '';
    const lenStr = `${f.length}/${f.max}`.padStart(10);
    lines.push(
      `${c}${f.status.padEnd(10)}${colors.RESET}  ${lenStr}  ${f.section} → ${f.name}`,
    );
    if (f.detail) lines.push(`  ${f.detail}`);
  }
  lines.push('─'.repeat(60));
  const fail = findings.filter((f) => ['OVER', 'MISSING', 'EMPTY'].includes(f.status));
  const warn = findings.filter((f) => f.status === 'NEAR_LIMIT');
  lines.push(
    fail.length === 0
      ? `${colors.OK}PASS${colors.RESET}  ${findings.length} fields within limits${warn.length ? ` (${warn.length} near cap)` : ''}`
      : `${colors.OVER}FAIL${colors.RESET}  ${fail.length} field(s) over limit / missing — fix before pasting into ASC`,
  );
  return lines.join('\n');
}

function main() {
  let md;
  try {
    md = readFileSync(ASO_PATH, 'utf8');
  } catch (e) {
    console.error(`ERROR: cannot read ${ASO_PATH} — ${e.message}`);
    process.exit(2);
  }

  const apple = parseListingSection(md, 'iOS App Store Connect');
  const play = parseListingSection(md, 'Google Play Store');

  // The Play "Short Description" + "Full Description" sections are
  // labelled differently than Apple's. Map them.
  const playFields = {
    'App Name': play['App Name'],
    'Short Description': play['Short Description'],
    'Full Description': play['Full Description'],
  };

  const findings = [
    ...checkLimits('iOS', apple, APPLE_LIMITS),
    ...checkLimits('Play', playFields, PLAY_LIMITS),
  ];

  console.log(render(findings));

  const fail = findings.some((f) =>
    ['OVER', 'MISSING', 'EMPTY'].includes(f.status),
  );
  process.exit(fail ? 1 : 0);
}

main();
