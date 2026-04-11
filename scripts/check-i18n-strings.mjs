#!/usr/bin/env node
/**
 * Untranslated-string lint check.
 *
 * Scans the app/ and src/ directories for TSX/TS files that contain likely
 * hardcoded English UI strings — specifically JSX text nodes and common
 * prop values (accessibilityLabel, placeholder, title) that look human.
 *
 * This is a heuristic, not a parser. It catches the long-tail cases that slip
 * past manual review during i18n migrations. Expected false positives are
 * listed in ALLOWLIST below.
 *
 * Usage:
 *   node scripts/check-i18n-strings.mjs             # all files
 *   node scripts/check-i18n-strings.mjs --file X    # single file
 *   node scripts/check-i18n-strings.mjs --quiet     # only show counts
 *
 * Exit codes:
 *   0 — no issues (or allowlisted files only)
 *   1 — untranslated strings found
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const SCAN_DIRS = ['app', 'src'];

// Files/directories to skip entirely. These are known-good (tests, legal copy,
// build artifacts, generated code, or files that should stay English).
const IGNORE_PATTERNS = [
  /node_modules/,
  /__tests__/,
  /\.test\.tsx?$/,
  /\.snapshot\.tsx?$/,
  /\.d\.ts$/,
  /i18n\/locales\//,
  /legal\//, // legal pages kept in English source of truth
  /condition-guide\//, // grading reference
  /constants\/categories/, // category keys are identifiers, not UI strings
];

// Props that commonly hold hardcoded English strings we want to flag.
// accessibilityHint & accessibilityValue excluded — rarely user-visible.
const FLAGGED_PROPS = [
  'accessibilityLabel',
  'placeholder',
  'title',
  'label',
  'alt',
];

// A string must look "human" to be flagged: at least one space OR be a
// multi-word CamelCase phrase. Single words and obvious identifiers are skipped.
const LOOKS_HUMAN = /^[A-Z][a-z].*\s|^[A-Z][a-z]+[A-Z][a-z]/;

// Exclusions: literal strings that are NOT user-visible UI.
const ALLOWLIST_STRINGS = new Set([
  'none', 'auto', 'transparent', 'padding', 'height', 'handled',
  'page-sheet', 'pageSheet', 'form-sheet',
  'light-content', 'dark-content',
  'search', 'default', 'email-address', 'number-pad', 'decimal-pad',
  'done', 'go', 'next', 'send', 'username-new', 'new-password',
  'image/png', 'public.png',
  'Arial', 'System',
]);

function walk(dir, out = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const name of entries) {
    const p = join(dir, name);
    if (IGNORE_PATTERNS.some((re) => re.test(p))) continue;
    const st = statSync(p);
    if (st.isDirectory()) {
      walk(p, out);
    } else if (/\.tsx?$/.test(name)) {
      out.push(p);
    }
  }
  return out;
}

/**
 * Scan one file for likely untranslated strings.
 * Returns an array of { line, col, text, context } findings.
 */
function scanFile(path) {
  const src = readFileSync(path, 'utf8');
  const lines = src.split('\n');
  const findings = [];

  // Skip files that don't actually render React/JSX — helpers/config/etc.
  if (!/<[A-Z]/.test(src) && !/return\s*\(/.test(src)) return findings;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    // Skip comments, imports, and t() calls.
    const trimmed = line.trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('*')) continue;
    if (/^import\b/.test(trimmed)) continue;

    // 1) JSX text content: >Text here<
    //    Captures text between > and < that isn't a JSX expression.
    const textNodeRe = />([^<>{}\n]+)</g;
    let m;
    while ((m = textNodeRe.exec(line)) !== null) {
      const raw = m[1].trim();
      if (!raw || raw.length < 3) continue;
      if (ALLOWLIST_STRINGS.has(raw)) continue;
      if (!LOOKS_HUMAN.test(raw)) continue;
      // Skip if text clearly contains interpolation only (no letters)
      if (!/[a-zA-Z]{3,}/.test(raw)) continue;
      findings.push({
        line: i + 1,
        col: m.index + 1,
        text: raw.slice(0, 80),
        kind: 'jsx-text',
      });
    }

    // 2) Flagged prop values: accessibilityLabel="Foo bar"
    for (const prop of FLAGGED_PROPS) {
      const propRe = new RegExp(`\\b${prop}\\s*=\\s*(["'])([^"'\\n]+?)\\1`, 'g');
      while ((m = propRe.exec(line)) !== null) {
        const val = m[2].trim();
        if (!val || val.length < 3) continue;
        if (ALLOWLIST_STRINGS.has(val)) continue;
        if (!LOOKS_HUMAN.test(val)) continue;
        if (!/[a-zA-Z]{3,}/.test(val)) continue;
        findings.push({
          line: i + 1,
          col: m.index + 1,
          text: `${prop}="${val.slice(0, 60)}"`,
          kind: 'prop',
        });
      }
    }
  }

  return findings;
}

function main() {
  const args = process.argv.slice(2);
  const quiet = args.includes('--quiet');
  const fileArgIdx = args.indexOf('--file');
  const singleFile = fileArgIdx >= 0 ? args[fileArgIdx + 1] : null;

  let files;
  if (singleFile) {
    files = [join(ROOT, singleFile)];
  } else {
    files = SCAN_DIRS.flatMap((d) => walk(join(ROOT, d)));
  }

  let totalFindings = 0;
  const perFile = [];
  for (const f of files) {
    const findings = scanFile(f);
    if (findings.length) {
      perFile.push({ file: relative(ROOT, f), findings });
      totalFindings += findings.length;
    }
  }

  if (!quiet) {
    for (const { file, findings } of perFile) {
      console.log(`\n${file}  (${findings.length})`);
      for (const f of findings.slice(0, 20)) {
        console.log(`  ${file}:${f.line}  [${f.kind}]  ${f.text}`);
      }
      if (findings.length > 20) {
        console.log(`  … and ${findings.length - 20} more`);
      }
    }
  }

  console.log(
    `\ni18n lint: ${totalFindings} untranslated string(s) across ${perFile.length} file(s) (${files.length} scanned)`,
  );

  if (totalFindings > 0) {
    console.log(
      '\nTip: wrap user-visible strings with t(\'namespace.key\') from useTranslation().',
    );
    process.exit(1);
  }
  process.exit(0);
}

main();
