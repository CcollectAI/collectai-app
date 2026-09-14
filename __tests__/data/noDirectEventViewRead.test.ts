/**
 * No app code may read `v_events_with_attendees_v1` directly.
 *
 * The view has no WHERE clause. Read through supabase-js it returns
 * newsletter-quarantined rows, quality-score rejects, non-published duplicates
 * and PRIVATE events, and its attendee counts are zero for every signed-in user
 * (security_invoker + event_attendees' deny-all RLS). Events are read through
 * the server (`GET /events`, `GET /events/{id}`), which applies status, date,
 * is_public and the display gate.
 *
 * getEventById was moved off it 2026-07-27 and eventsProvider.ts said that was
 * "the last direct supabase-js read of that view". It was not: the category
 * page's events section still read it, and on 2026-09-14 Sports Cards opened on
 * "12. Cruz roja argentina", a scraped newsletter row the feed had hidden for
 * seven weeks. A comment saying "the last one" is not a check; this is.
 */
import { readdirSync, readFileSync, statSync } from 'fs';
import { join } from 'path';

const ROOT = join(__dirname, '..', '..');
const VIEW = 'v_events_with_attendees_v1';

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (name === 'node_modules' || name === '__tests__' || name.startsWith('.')) continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(ts|tsx)$/.test(name)) out.push(p);
  }
  return out;
}

/** Strip comments so documentation that NAMES the view does not count as a read. */
function code(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
}

describe('events are never read from the ungated view', () => {
  it(`no file under src/ or app/ references ${VIEW} outside a comment`, () => {
    const files = [...walk(join(ROOT, 'src')), ...walk(join(ROOT, 'app'))];
    expect(files.length).toBeGreaterThan(100); // the walk actually found the app
    const offenders = files
      .filter((f) => !f.includes(`${join('src', 'data', 'mocks')}`))
      .filter((f) => code(readFileSync(f, 'utf8')).includes(VIEW))
      .map((f) => f.slice(ROOT.length + 1));
    expect(offenders).toEqual([]);
  });
});
