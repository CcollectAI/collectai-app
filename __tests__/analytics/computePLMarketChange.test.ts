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

it('a series starting at zero, WITHOUT market_change, still has no baseline', () => {
  const noBase = [{ t: '2026-09-01T00:00:00Z', v: 0 }, { t: '2026-09-26T00:00:00Z', v: 1253 }];
  expect(computePLFromSeries(noBase).deltaAbs).toBe(0);
  expect(computePLFromSeries(noBase).hasBaseline).toBe(false);
});

it('with market_change, a series starting at zero measures from what the items entered at (90D, prod)', () => {
  // This test used to assert 0 here "whatever market_change says" — pinning the
  // bug: on 90D the chart starts before anything was owned, and a EUR 35 fall
  // after purchase read as no change. Basis = current - market_change.
  const ninety = [
    { t: '2026-06-28T00:00:00Z', v: 0 },
    { t: '2026-08-27T00:00:00Z', v: 1263.29 },
    { t: '2026-09-26T00:00:00Z', v: 1228 },
  ];
  const pl = computePLFromSeries(ninety, -35.29);
  expect(pl.hasBaseline).toBe(true);
  expect(pl.deltaAbs).toBeCloseTo(-35.29);
  expect(pl.startValue).toBeCloseTo(1263.29);
  expect(pl.deltaPct).toBeCloseTo(-35.29 / 1263.29, 6);
});
