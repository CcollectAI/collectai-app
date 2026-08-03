/**
 * The portfolio chart's y-axis, pinned against the real screenshots that
 * reported it broken (2026-08-03).
 *
 * The bug: `formatPrice` renders 0 decimals app-wide (deliberate, see
 * lib/format.ts), so ANY domain narrower than a couple of currency units
 * collapses every gridline label to the same string. A portfolio sitting at
 * EUR 55 that moved one cent produced three ticks that all printed "EUR 55",
 * and the line spanned the full canvas height over that cent — which is why it
 * also looked glued to the top of the frame.
 *
 * These assert the OUTPUT the user sees (distinct labels, low → high), not the
 * internal arithmetic, so they keep biting if the rounding is reworked.
 */
import { niceScale } from '@/components/PortfolioLineChart';

/** Mirrors formatPrice's contract: whole currency units, no decimals. */
const label = (v: number) => `EUR ${Math.round(v)}`;

describe('portfolio chart y-axis scale', () => {
  it('gives a near-flat series distinct labels (the EUR 55 screenshot)', () => {
    // Exactly the reported case: EUR 55 portfolio, -0.02% over the range.
    const { ticks } = niceScale(54.99, 55.0);

    const labels = ticks.map(label);
    expect(new Set(labels).size).toBe(labels.length);
    expect(ticks.length).toBeGreaterThanOrEqual(2);
  });

  it('orders ticks low → high', () => {
    const { ticks } = niceScale(54.99, 55.0);
    const ascending = [...ticks].sort((a, b) => a - b);
    expect(ticks).toEqual(ascending);
  });

  it('leaves the value room to breathe rather than pinning it to an edge', () => {
    // The value must land strictly INSIDE the domain, else the line draws on
    // the frame and reads as cut off.
    const { yMin, yMax } = niceScale(54.99, 55.0);
    expect(yMin).toBeLessThan(54.99);
    expect(yMax).toBeGreaterThan(55.0);
  });

  it('never emits ticks closer than one currency unit', () => {
    // The generalisation: sub-unit steps are what produced duplicate labels.
    for (const [lo, hi] of [
      [54.99, 55.0],
      [10.0, 10.02],
      [0.5, 0.51],
      [999.1, 999.2],
    ]) {
      const { ticks } = niceScale(lo, hi);
      for (let i = 1; i < ticks.length; i++) {
        expect(ticks[i] - ticks[i - 1]).toBeGreaterThanOrEqual(1);
      }
    }
  });

  it('still behaves for a genuinely wide range (the EUR 8.070 screenshot)', () => {
    // A real spread must NOT be widened into nonsense — 0 → 8070 should keep
    // recognisable round gridlines.
    const { yMin, yMax, ticks } = niceScale(0, 8070);
    expect(yMin).toBe(0);
    expect(yMax).toBeGreaterThanOrEqual(8070);
    expect(new Set(ticks.map(label)).size).toBe(ticks.length);
  });

  it('handles an exactly-flat series', () => {
    const { yMin, yMax, ticks } = niceScale(55, 55);
    expect(yMin).toBeLessThan(55);
    expect(yMax).toBeGreaterThan(55);
    expect(new Set(ticks.map(label)).size).toBe(ticks.length);
  });

  it('does not send a non-negative measure below zero', () => {
    const { yMin } = niceScale(0, 0);
    expect(yMin).toBeGreaterThanOrEqual(0);
  });
});
