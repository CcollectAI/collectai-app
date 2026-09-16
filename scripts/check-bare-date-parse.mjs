#!/usr/bin/env node
/**
 * A bare `YYYY-MM-DD` parsed by `new Date()` is UTC MIDNIGHT, not local.
 *
 * `events.date` is a bare date with the clock in a separate `time` column (all
 * 3,285 prod rows). So `new Date(event.date) < new Date()` is true from
 * 02:00 CEST on the event's OWN day — and from 17:00 the day BEFORE in Los
 * Angeles. It has bitten three times:
 *   2026-09-12 the event screen hid Going/Interested for an event that evening;
 *   2026-09-16 (class sweep) the sponsor dashboard's "active campaigns" KPI,
 *   the campaigns table's "Past" label, and the announcement composer's chip.
 *
 * `src/lib/calendar.ts` holds the answers: `isEventPast(date, time, endDate)`,
 * `parseEventDate(date)` (LOCAL midnight) and `formatEventWhen(...)`.
 *
 * This gate flags `new Date(<something>.date | endDate | startDate | eventDate)`
 * outside calendar.ts. Exempt a genuine timestamptz (a full ISO string with a
 * zone — `created_at`, `soldAt`) with a reason:
 *     // date-ok: created_at is timestamptz, so new Date() is exact
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

// `new Date(x.date)`, `new Date(evt.endDate)`, `new Date(event?.startDate)`.
// A bare local variable is not matched: only a FIELD named like a bare date,
// which is what the backend actually serves.
const BARE_DATE_FIELD = /new Date\(\s*[\w$.?[\]]*\.(date|endDate|startDate|eventDate|dropDate)\b/;

const findings = [];
for (const abs of SCAN.flatMap((d) => walk(join(ROOT, d)))) {
  const rel = relative(ROOT, abs);
  if (rel === 'src/lib/calendar.ts') continue; // defines parseEventDate/isEventPast
  const lines = readFileSync(abs, 'utf8').split('\n');
  lines.forEach((line, i) => {
    const code = line.replace(/\/\/.*$/, '');
    if (!BARE_DATE_FIELD.test(code)) return;
    const near = lines.slice(Math.max(0, i - 3), i + 1).join('\n');
    if (/date-ok:/.test(near)) return;
    findings.push(`${rel}:${i + 1}  ${line.trim().slice(0, 100)}`);
  });
}

if (findings.length) {
  console.error(`✗ bare-date parse — ${findings.length} site(s) parse a bare YYYY-MM-DD as UTC midnight:`);
  for (const f of findings) console.error(`   ${f}`);
  console.error('\n   Use isEventPast(date, time, endDate) / parseEventDate(date) from src/lib/calendar.ts,');
  console.error('   or add "// date-ok: <why this field is a full timestamp>".');
  process.exit(1);
}
console.log('✓ bare-date parse — every bare date goes through calendar.ts, or says why it need not.');
