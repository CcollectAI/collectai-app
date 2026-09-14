/**
 * Whether the Events tab's calendar views should fetch another page.
 *
 * Week and Month filter LOADED events by day, so they need every upcoming
 * event. Without this the Month view showed November empty on 2026-09-14 while
 * prod held 100 events between Oct 14 and Nov 22 — page one (the server's max,
 * 100) ended on Oct 13.
 *
 * Never while a fetch is running (loadMore would no-op, but the effect must
 * not spin), never after an error (it stays set until refresh, so continuing
 * would retry forever), and never past `maxEvents`.
 */
export const CALENDAR_MAX_EVENTS = 1000;

export function shouldPageCalendar(s: {
  calendarView: boolean;
  hasMore: boolean;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  loadedCount: number;
  maxEvents?: number;
}): boolean {
  if (!s.calendarView || !s.hasMore || s.loading || s.loadingMore || s.error) return false;
  return s.loadedCount < (s.maxEvents ?? CALENDAR_MAX_EVENTS);
}
