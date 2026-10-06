/**
 * The shared market-source list and the "last seen" date (2026-10-06).
 *
 * The list used to exist three times (ValueSourceChip, portfolioAnalytics,
 * Home). These tests pin the one copy, and the chip's honest wording for the
 * new `catalog_price` link of public.item_value_v1.
 */
import { setActiveDateLocale } from '@/constants/dateFormats';
import { MARKET_VALUE_SOURCES, isMarketBacked, formatValueAsOf } from '@/lib/valueSources';
import { describeValueSource, isMarketBacked as chipIsMarketBacked } from '@/components/ValueSourceChip';

describe('MARKET_VALUE_SOURCES', () => {
  it('counts the catalogue price as market-derived, never the member\'s guesses', () => {
    expect(isMarketBacked('catalog_price')).toBe(true);
    for (const s of ['catalog_daily', 'catalog_model', 'quick_scan']) expect(isMarketBacked(s)).toBe(true);
    for (const s of ['user_estimate', 'app_estimate', 'none', '', null, undefined]) {
      expect(isMarketBacked(s as string | null | undefined)).toBe(false);
    }
  });

  it('is the same list the chip uses (one definition, not three)', () => {
    for (const s of MARKET_VALUE_SOURCES) expect(chipIsMarketBacked(s)).toBe(true);
    expect(chipIsMarketBacked('user_estimate')).toBe(false);
  });
});

describe('describeValueSource', () => {
  it('labels catalog_price as what it is, not as a model estimate', () => {
    expect(describeValueSource('catalog_price')).toEqual({ label: 'Catalogue price', tone: 'market' });
    expect(describeValueSource('catalog_model')?.label).toBe('Market estimate');
  });
});

describe('formatValueAsOf', () => {
  afterEach(() => setActiveDateLocale(null));

  it('formats a bare date as the LOCAL day in the app language', () => {
    setActiveDateLocale('en-GB');
    expect(formatValueAsOf('2026-08-18')).toBe('18 Aug');
    setActiveDateLocale('nl-NL');
    expect(formatValueAsOf('2026-08-18')).toMatch(/^18 aug/);
  });

  it('returns null rather than "Invalid Date" for missing or unreadable input', () => {
    expect(formatValueAsOf(null)).toBeNull();
    expect(formatValueAsOf('')).toBeNull();
    expect(formatValueAsOf('not-a-date')).toBeNull();
  });
});
