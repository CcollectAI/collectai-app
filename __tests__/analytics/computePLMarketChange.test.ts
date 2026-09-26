/**
 * 2026-09-26: items ADDED in the window are not a gain. With a baseline, the
 * server's market_change wins over last-minus-first; without one, still 0.
 */
import { computePLFromSeries } from '../../src/analytics/portfolioMetrics';

const series = [
  { t: '2026-09-01T00:00:00Z', v: 1228 },
  { t: '2026-09-26T00:00:00Z', v: 1253 },
];

it('uses market_change for the delta when given', () => {
  const pl = computePLFromSeries(series, 0);
  expect(pl.deltaAbs).toBe(0);
  expect(pl.currentValue).toBe(1253);
});

it('keeps last-minus-first when market_change is absent', () => {
  expect(computePLFromSeries(series).deltaAbs).toBe(25);
});

it('a series with no baseline stays at zero, whatever market_change says', () => {
  const noBase = [{ t: '2026-09-01T00:00:00Z', v: 0 }, { t: '2026-09-26T00:00:00Z', v: 1253 }];
  expect(computePLFromSeries(noBase, 50).deltaAbs).toBe(0);
});
