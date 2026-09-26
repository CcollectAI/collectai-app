/**
 * Adding an item is not a gain (2026-09-26). Measured on prod, simcheck, 7D:
 * first 1228, last 1253 — the EUR 25 was an item ADDED in the window, and the
 * server's market_change for the same range is 0.
 */
import { portfolioChange, extractMarketChange } from '../../src/lib/portfolioChange';

const series = [{ t: '2026-09-19', v: 1228 }, { t: '2026-09-26', v: 1253 }];

it('uses the market change when the server sends it', () => {
  expect(portfolioChange(series, 0)).toEqual({ total: 1253, delta: 0, deltaPct: 0 });
  // Against what the items were worth when they entered: 1253 + 35.29.
  expect(portfolioChange(series, -35.29).deltaPct).toBeCloseTo(-35.29 / 1288.29, 6);
});

it('falls back to last minus first when it is absent', () => {
  expect(portfolioChange(series, null).delta).toBe(25);
});

it('reads market_change only when it is a finite number', () => {
  expect(extractMarketChange({ points: [], market_change: 12.5 })).toBe(12.5);
  expect(extractMarketChange({ points: [] })).toBeNull();
  expect(extractMarketChange({ market_change: 'x' })).toBeNull();
});

it('a range that starts before anything was owned still has a percent (90D, prod)', () => {
  const ninety = [{ t: '2026-06-28', v: 0 }, { t: '2026-08-27', v: 1263.29 }, { t: '2026-09-26', v: 1228 }];
  expect(portfolioChange(ninety, -35.29).deltaPct).toBeCloseTo(-35.29 / 1263.29, 6);
});
