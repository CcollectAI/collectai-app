/**
 * Leaderboard display seam.
 *
 * `/gamification/leaderboard` is an **XP** board: each entry carries
 * `total_xp`, `level`, `current_streak`. Until 2026-07-31 the screen poured
 * those into the shape of the local `USER_PROFILES` sample, which ranks by
 * collection value — `totalEstimatedValueEur: entry.xp` — and the card renders
 * that field through `formatPrice`. So against the live board a collector with
 * 80 XP was displayed as **"€80.00"**, their level as "1 item", and every row
 * read "0 categories".
 *
 * Nothing caught it: the endpoint returned 200, the types were satisfied
 * (both numbers), and the screen rendered without error. Only comparing the
 * VALUE to its meaning finds this class.
 *
 * The three entries below are the live prod board (period=alltime, 2026-07-31).
 */
import { apiEntryToRow } from '../../app/leaderboard';

/** Live prod payload: GET /gamification/leaderboard?period=alltime */
const PROD_BOARD = [
  { rank: 1, user_id: '20503ad2-c62d-4700-810b-36da247bbf28', display_name: null, total_xp: 80, level: 1, current_streak: 1 },
  { rank: 2, user_id: 'b4271bd3-b872-435c-a5f4-44d598f8d479', display_name: null, total_xp: 40, level: 1, current_streak: 2 },
  { rank: 3, user_id: '00000000-0000-0000-0000-000000000003', display_name: null, total_xp: 10, level: 1, current_streak: 0 },
];

describe('apiEntryToRow — XP must never render as currency', () => {
  it('renders XP as XP, not money', () => {
    const row = apiEntryToRow(PROD_BOARD[0]);
    expect(row.primary).toBe('80 XP');
    expect(row.primary).not.toMatch(/[€$£¥]/);
  });

  it('no row on the live board renders a currency symbol anywhere', () => {
    for (const entry of PROD_BOARD) {
      const row = apiEntryToRow(entry);
      for (const field of [row.primary, row.secondary, row.meta]) {
        expect(field).not.toMatch(/[€$£¥]/);
      }
    }
  });

  it('reports level as a level, not an item count', () => {
    const row = apiEntryToRow(PROD_BOARD[0]);
    expect(row.secondary).toBe('Level 1');
    expect(row.secondary).not.toMatch(/item/i);
    expect(row.meta).not.toMatch(/categor/i); // the hardcoded "0 categories"
  });

  it('surfaces the streak the API returns, including the zero case', () => {
    expect(apiEntryToRow(PROD_BOARD[1]).meta).toBe('2 day streak');
    expect(apiEntryToRow(PROD_BOARD[2]).meta).toBe('No active streak');
  });

  it('falls back to a rank-based name when display_name is null', () => {
    // Every prod profile currently has a null display_name (legacy accounts).
    expect(apiEntryToRow(PROD_BOARD[0]).displayName).toBe('Collector 1');
    expect(apiEntryToRow(PROD_BOARD[0]).handle).toBe('collector1');
  });

  it('uses a real display_name when one exists, and never emits a null handle', () => {
    const row = apiEntryToRow({ ...PROD_BOARD[0], display_name: 'Merle S' });
    expect(row.displayName).toBe('Merle S');
    expect(row.handle).toBe('merles');
  });

  /*
   * Locale must come from `user_settings.locale` (NumberLocale), never from the
   * device. Until 2026-08-10 this read `entry.total_xp.toLocaleString()` with no
   * locale, so the SAME code produced "12.500 XP" on a Dutch machine and
   * "12,500 XP" on a US one — and this test passed or failed depending on whose
   * terminal ran it, which is why it looked flaky rather than broken.
   *
   * Pin the locale explicitly on every assertion here. ko-KR and en-AU are the
   * newest NumberLocale values (added 2026-07-30) and the least exercised.
   */
  it('thousands-separates large XP totals in the user-selected locale', () => {
    expect(apiEntryToRow({ ...PROD_BOARD[0], total_xp: 12500 }, 'en-US').primary).toBe('12,500 XP');
    expect(apiEntryToRow({ ...PROD_BOARD[0], total_xp: 12500 }, 'de-DE').primary).toBe('12.500 XP');
    expect(apiEntryToRow({ ...PROD_BOARD[0], total_xp: 12500 }, 'ja-JP').primary).toBe('12,500 XP');
    expect(apiEntryToRow({ ...PROD_BOARD[0], total_xp: 12500 }, 'ko-KR').primary).toBe('12,500 XP');
    expect(apiEntryToRow({ ...PROD_BOARD[0], total_xp: 12500 }, 'en-AU').primary).toBe('12,500 XP');
    expect(apiEntryToRow({ ...PROD_BOARD[0], total_xp: 12500 }, 'nl-NL').primary).toBe('12.500 XP');
  });

  /*
   * The small-number assertions above call apiEntryToRow with no locale, so they
   * exercise the 'de-DE' default. That default must match
   * DEFAULT_SETTINGS.numberLocale in src/lib/settings.tsx.
   */
  it('defaults to the app-wide default locale when none is passed', () => {
    expect(apiEntryToRow({ ...PROD_BOARD[0], total_xp: 12500 }).primary).toBe('12.500 XP');
  });
});
