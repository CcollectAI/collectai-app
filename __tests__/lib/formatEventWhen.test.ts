/**
 * `formatEventWhen` — the one formatter every event surface prints its date
 * through (list card, detail hero, nearby row, share text, two a11y labels).
 *
 * WHY THIS TEST EXISTS (2026-09-09): those six places each interpolated the raw
 * backend fields, so the Events tab read "Convention • 2026-09-11 — 20:00:00"
 * on every row. The regression that matters most is not the format — it is the
 * DEGRADE rule: a time we cannot parse must cost the time, never the date.
 */
import { formatEventWhen } from '@/lib/calendar';

const ISO_DATE = /\d{4}-\d{2}-\d{2}/;

describe('formatEventWhen', () => {
  it('never prints a raw ISO date or seconds for a well-formed event', () => {
    const out = formatEventWhen('2026-09-11', '20:00:00');
    expect(out).not.toMatch(ISO_DATE);
    expect(out).not.toMatch(/:\d{2}:\d{2}/); // no seconds
    expect(out).toContain('2026');
    expect(out).toContain('Sep');
  });

  it('keeps the date when the time is unparseable — degrade precision, not existence', () => {
    const out = formatEventWhen('2026-09-11', 'doors when ready');
    expect(out).toContain('Sep');
    expect(out).toContain('11');
    expect(out).toContain('2026');
    expect(out).not.toMatch(ISO_DATE);
  });

  it('renders a date-only event without inventing a midnight time', () => {
    const out = formatEventWhen('2026-09-11');
    expect(out).not.toContain('00:00');
    expect(out).not.toContain('12:00');
    expect(out).toContain('Sep');
  });

  it('falls back to the raw string rather than blanking an unknown date shape', () => {
    expect(formatEventWhen('sometime in spring')).toBe('sometime in spring');
  });

  it('returns empty for a missing date', () => {
    expect(formatEventWhen('')).toBe('');
    expect(formatEventWhen(null)).toBe('');
    expect(formatEventWhen(undefined)).toBe('');
  });

  it('takes both halves from the same instant when the time carries a timezone', () => {
    // 23:30 JST on the 11th is the 11th at 14:30 UTC — whatever the viewer's
    // zone, the printed day must be the day of the printed clock, not the raw
    // input's day paired with a converted time.
    const out = formatEventWhen('2026-09-11', '23:30 JST');
    const asDate = new Date(Date.UTC(2026, 8, 11, 14, 30));
    expect(out).toContain(
      asDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
    );
  });
});
