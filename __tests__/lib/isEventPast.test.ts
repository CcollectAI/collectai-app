/**
 * An event happening TONIGHT is not over.
 *
 * WHY (2026-09-12, found walking the app on Android): the event detail screen
 * computed `new Date(event.endDate || event.date) < new Date()`. Every event
 * row in prod stores a BARE date (`YYYY-MM-DD`, 3,285 of 3,285) with the clock
 * in a separate `time` column, and JS parses a bare date as **UTC midnight**:
 *
 *     new Date('2026-09-12')  ->  2026-09-12T00:00:00Z
 *
 * So from roughly 01:00 CEST every event happening that day counted as past,
 * and the screen rendered its past branch — Share only, no Going, no
 * Interested. **You could not RSVP to anything happening today.** Meanwhile the
 * LIST, which uses `parseEventDate(date, time)`, still showed it under
 * "Upcoming": two screens disagreeing about one event.
 *
 * The case that matters is the first test. The rest exist so the fix cannot be
 * "never past", which would be just as wrong in the other direction.
 */
import { isEventPast } from '@/lib/calendar';

// Midday, so a bare-date parse lands in the past while an evening event has not
// started. This is exactly the window the bug lived in.
const NOON = new Date('2026-09-12T12:00:00');

describe('isEventPast', () => {
  it('an event LATER TODAY is not past — the bug', () => {
    expect(isEventPast('2026-09-12', '20:00:00', null, NOON)).toBe(false);
  });

  it('a timeless event today matches the LIST: past once local midnight passes', () => {
    // This assertion started life as `false` — my preference, not the system's
    // rule. `(tabs)/events.tsx` splits upcoming from past with the same
    // `parseEventDate(date, time)`, so a date-only event today is already out
    // of "Upcoming" there. Making the detail disagree would reintroduce exactly
    // the split this fix exists to close, so the shared helper matches the list
    // and the test records the real behaviour.
    //
    // ⚠️ OPEN QUESTION, deliberately not decided here: arguably an all-day
    // event should run until END of day rather than vanish at 00:01. That is a
    // product call and it would have to change the LIST too — one expression,
    // both screens.
    expect(isEventPast('2026-09-12', null, null, NOON)).toBe(true);
  });

  it('an event EARLIER today IS past', () => {
    expect(isEventPast('2026-09-12', '08:00:00', null, NOON)).toBe(true);
  });

  it('yesterday is past', () => {
    expect(isEventPast('2026-09-11', '20:00:00', null, NOON)).toBe(true);
  });

  it('tomorrow is not past', () => {
    expect(isEventPast('2026-09-13', '08:00:00', null, NOON)).toBe(false);
  });

  it('a multi-day event runs until its END date', () => {
    expect(isEventPast('2026-09-10', '09:00:00', '2026-09-14', NOON)).toBe(false);
    expect(isEventPast('2026-09-08', '09:00:00', '2026-09-11', NOON)).toBe(true);
  });

  it('never claims an unparseable date is over', () => {
    // "Could not tell" must not render an event as finished and hide its RSVP.
    expect(isEventPast('sometime in spring', null, null, NOON)).toBe(false);
    expect(isEventPast('', null, null, NOON)).toBe(false);
  });
});
