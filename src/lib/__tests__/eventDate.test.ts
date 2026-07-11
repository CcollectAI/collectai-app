import { parseIso, toIso, formatDMY } from '../eventDate';

describe('eventDate helpers', () => {
  describe('formatDMY (ISO → display)', () => {
    it('reformats a valid ISO date to DD-MM-YYYY', () => {
      expect(formatDMY('2026-01-09')).toBe('09-01-2026');
      expect(formatDMY('2026-12-31')).toBe('31-12-2026');
    });
    it('returns empty string for empty/invalid input', () => {
      expect(formatDMY('')).toBe('');
      expect(formatDMY('   ')).toBe('');
      expect(formatDMY('09-01-2026')).toBe(''); // already DMY, not ISO
      expect(formatDMY('nonsense')).toBe('');
    });
    it('trims surrounding whitespace', () => {
      expect(formatDMY('  2026-06-15  ')).toBe('15-06-2026');
    });
  });

  describe('parseIso (ISO → Date)', () => {
    it('parses a valid ISO date to the right local Y/M/D', () => {
      const d = parseIso('2026-03-07');
      expect(d).not.toBeNull();
      expect(d!.getFullYear()).toBe(2026);
      expect(d!.getMonth()).toBe(2); // March = index 2
      expect(d!.getDate()).toBe(7);
    });
    it('returns null for malformed, empty, or out-of-range input', () => {
      expect(parseIso('')).toBeNull();
      expect(parseIso('2026-13-40')).toBeNull(); // month 13 / day 40 — rejected, not rolled over
      expect(parseIso('2026-02-29')).toBeNull(); // 2026 is NOT a leap year — Feb 29 invalid
      expect(parseIso('09-01-2026')).toBeNull();
      expect(parseIso('garbage')).toBeNull();
    });
  });

  describe('toIso (Date → ISO)', () => {
    it('formats with zero-padded month and day', () => {
      expect(toIso(new Date(2026, 0, 5))).toBe('2026-01-05'); // Jan 5
      expect(toIso(new Date(2026, 8, 30))).toBe('2026-09-30'); // Sep 30
    });
  });

  describe('round-trip (no UTC off-by-one)', () => {
    // The whole point of storing ISO but picking via a Date object: the day you
    // tap must be the day stored, regardless of the machine's timezone. If parse
    // or format used UTC, Jan 1 could drift to Dec 31.
    const cases = ['2026-01-01', '2026-12-31', '2024-02-29', '2026-06-15', '2026-11-01'];
    it.each(cases)('iso → parseIso → toIso is stable for %s', (iso) => {
      const d = parseIso(iso);
      expect(d).not.toBeNull();
      expect(toIso(d!)).toBe(iso);
    });
  });

  it('display of a round-tripped picker value matches DD-MM-YYYY', () => {
    // Simulate: stored ISO → picker Date → user keeps it → stored back → displayed.
    const stored = '2024-02-29'; // real leap day (2024 IS a leap year)
    const picked = parseIso(stored)!;
    const restored = toIso(picked);
    expect(restored).toBe('2024-02-29');
    expect(formatDMY(restored)).toBe('29-02-2024');
  });
});
