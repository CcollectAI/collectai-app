/**
 * The three numbers a collection has — what you PAID, what the MARKET says,
 * and what somebody ESTIMATED (decided 2026-08-19).
 *
 * They are not three versions of one figure: one is a fact about the past, one
 * is a claim we can back with comps, and one is an opinion. Collapsing the
 * first two is how `unrealized_pl` came to measure model drift instead of
 * profit; presenting the third as the second is what `value_source` exists to
 * stop.
 */
import { splitPortfolioByValueSource } from '@/lib/portfolioAnalytics';

const item = (over: Record<string, unknown> = {}) => ({
  id: 'i', name: 'n', currentValue: 100, costBasis: 60, hasPurchasePrice: true,
  valueSource: 'catalog_model', ...over,
});

describe('splitPortfolioByValueSource', () => {
  it('counts the comp/model-backed sources as market', () => {
    for (const s of ['catalog_daily', 'catalog_model', 'quick_scan']) {
      const r = splitPortfolioByValueSource([item({ valueSource: s })]);
      expect(r.marketTotal).toBe(100);
      expect(r.estimateTotal).toBe(0);
      expect(r.marketCount).toBe(1);
    }
  });

  it('counts a typed or scanned number as an estimate, not as market', () => {
    for (const s of ['user_estimate', 'app_estimate', 'none']) {
      const r = splitPortfolioByValueSource([item({ valueSource: s })]);
      expect(r.estimateTotal).toBe(100);
      expect(r.marketTotal).toBe(0);
    }
  });

  it('treats an UNKNOWN source as an estimate — the under-claiming side', () => {
    // Older server builds send no value_source. Defaulting to "market" would
    // let the app assert comps it does not have.
    const r = splitPortfolioByValueSource([item({ valueSource: undefined })]);
    expect(r.estimateTotal).toBe(100);
    expect(r.marketTotal).toBe(0);
  });

  it('keeps the estimated portion IN the total rather than dropping it', () => {
    // For the 40+ categories with no sold-comp source the estimate is all a
    // member has. Include and mark; hiding it shows a collection worth less
    // than they know it is.
    const r = splitPortfolioByValueSource([
      item({ valueSource: 'catalog_model', currentValue: 300 }),
      item({ valueSource: 'user_estimate', currentValue: 200 }),
    ]);
    expect(r.marketTotal + r.estimateTotal).toBe(500);
    expect(r.marketCount).toBe(1);
    expect(r.estimateCount).toBe(1);
  });

  it('only sums a REAL purchase price into what you paid', () => {
    // Without hasPurchasePrice the server falls back to the earliest prediction
    // as cost basis. Summing that reports money the member never spent.
    const r = splitPortfolioByValueSource([
      item({ costBasis: 60, hasPurchasePrice: true }),
      item({ costBasis: 999, hasPurchasePrice: false }),
    ]);
    expect(r.purchaseTotal).toBe(60);
    expect(r.purchaseCount).toBe(1);
  });

  it('returns zeroes for an empty collection rather than throwing', () => {
    const r = splitPortfolioByValueSource([]);
    expect(r).toEqual({
      purchaseTotal: 0, marketTotal: 0, estimateTotal: 0,
      purchaseCount: 0, marketCount: 0, estimateCount: 0,
    });
  });
});
