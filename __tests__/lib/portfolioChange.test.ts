/**
 * Adding an item is not a gain (2026-09-26). Measured on prod, simcheck, 7D:
 * first 1228, last 1253 — the EUR 25 was an item ADDED in the window, and the
 * server's market_change for the same range is 0.
 */
import { portfolioChange, extractMarketChange } from '../../src/lib/portfolioChange';

const series = [{ t: '2026-09-19', v: 1228 }, { t: '2026-09-26', v: 1253 }];

it('uses the market change when the server sends it', () => {
  expect(portfolioChange(series, 0)).toEqual({ total: 1253, delta: 0, deltaPct: 0 });
  expect(portfolioChange(series, -35.29).deltaPct).toBeCloseTo(-35.29 / 1228);
});

it('falls back to last minus first when it is absent', () => {
  expect(portfolioChange(series, null).delta).toBe(25);
});

it('reads market_change only when it is a finite number', () => {
  expect(extractMarketChange({ points: [], market_change: 12.5 })).toBe(12.5);
  expect(extractMarketChange({ points: [] })).toBeNull();
  expect(extractMarketChange({ market_change: 'x' })).toBeNull();
});
