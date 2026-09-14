/**
 * The Events tab's Week/Month views page in every upcoming event.
 * Walked 2026-09-14: November rendered empty because only page one (to Oct 13)
 * was loaded. See src/lib/calendarPaging.ts.
 */
import { shouldPageCalendar, CALENDAR_MAX_EVENTS } from '@/lib/calendarPaging';

const base = { calendarView: true, hasMore: true, loading: false, loadingMore: false, error: null, loadedCount: 100 };

describe('shouldPageCalendar', () => {
  it('pages while a calendar view is open and the server has more', () => {
    expect(shouldPageCalendar(base)).toBe(true);
  });
  it('does not page in List mode (that pages on scroll)', () => {
    expect(shouldPageCalendar({ ...base, calendarView: false })).toBe(false);
  });
  it('stops when the server has no more', () => {
    expect(shouldPageCalendar({ ...base, hasMore: false })).toBe(false);
  });
  it('never fires while a fetch is running', () => {
    expect(shouldPageCalendar({ ...base, loading: true })).toBe(false);
    expect(shouldPageCalendar({ ...base, loadingMore: true })).toBe(false);
  });
  it('stops after an error instead of retrying forever', () => {
    expect(shouldPageCalendar({ ...base, error: 'Timed out loading. Pull to refresh.' })).toBe(false);
  });
  it('stops at the cap', () => {
    expect(shouldPageCalendar({ ...base, loadedCount: CALENDAR_MAX_EVENTS })).toBe(false);
    expect(shouldPageCalendar({ ...base, loadedCount: CALENDAR_MAX_EVENTS - 1 })).toBe(true);
  });
});
