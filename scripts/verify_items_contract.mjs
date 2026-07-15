#!/usr/bin/env node
/**
 * Live Supabase contract check for the items-list query.
 *
 * Runs the EXACT `ITEMS_SELECT` string that
 * src/data/providers/itemsProvider.ts sends, against the live PostgREST
 * endpoint, and asserts it resolves (HTTP 200 — not a 400 column-drift error).
 *
 * Why: `listItems()` wraps its query in a try/catch that returns [] on error.
 * So if a selected column is renamed/dropped, PostgREST 400s, the catch
 * swallows it, and the collection silently shows empty — no crash, no log the
 * user sees. This check turns that silent failure into a loud one. It reads the
 * select string from source (regex) so it can never drift from the real query.
 *
 * Read-only: anon key, limit 1. Exit 0 = pass, 1 = fail, 0 = skip (no creds).
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

function loadEnv(file) {
  const out = {};
  try {
    for (const line of readFileSync(join(root, file), 'utf8').split('\n')) {
      const t = line.trim();
      if (!t || t.startsWith('#') || !t.includes('=')) continue;
      const i = t.indexOf('=');
      out[t.slice(0, i).trim()] = t.slice(i + 1).trim().replace(/^["']|["']$/g, '');
    }
  } catch {
    /* no such file — fine */
  }
  return out;
}

const env = loadEnv('.env');
const SUPABASE_URL = env.EXPO_PUBLIC_SUPABASE_URL || env.SUPABASE_URL;
const ANON = env.EXPO_PUBLIC_SUPABASE_ANON_KEY || env.SUPABASE_ANON_KEY;

if (!SUPABASE_URL || !ANON) {
  console.warn('[items-contract] SKIP — no Supabase URL / anon key in .env');
  process.exit(0);
}

// Read the live ITEMS_SELECT from source so this check never drifts from it.
const src = readFileSync(join(root, 'src/data/providers/itemsProvider.ts'), 'utf8');
const m = src.match(/const ITEMS_SELECT\s*=\s*'([^']+)'/);
if (!m) {
  console.error('[items-contract] FAIL — could not locate ITEMS_SELECT in itemsProvider.ts');
  process.exit(1);
}
const SELECT = m[1];

const url = `${SUPABASE_URL}/rest/v1/items?select=${encodeURIComponent(SELECT)}&limit=1`;

try {
  const res = await fetch(url, {
    headers: { apikey: ANON, Authorization: `Bearer ${ANON}` },
  });
  if (res.status === 200) {
    console.log('[items-contract] PASS — ITEMS_SELECT resolves against the live DB (HTTP 200)');
    process.exit(0);
  }
  const body = await res.text();
  console.error(`[items-contract] FAIL — query rejected (HTTP ${res.status}). A selected column likely drifted from the live schema:`);
  console.error(body.slice(0, 500));
  process.exit(1);
} catch (e) {
  console.error('[items-contract] ERROR — could not reach Supabase:', e.message);
  process.exit(1);
}
