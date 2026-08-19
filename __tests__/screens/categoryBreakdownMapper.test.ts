/**
 * The seam between `/analytics/portfolio/category-breakdown` and the chart.
 *
 * The server is self-consistent and tested (`test_trends_and_deepdive_router.py`
 * pins `pct_of_portfolio == 0.625` for a category worth 62.5%). The component is
 * self-consistent — it renders `percentage.toFixed(0)}%` and a bar
 * `width: ${percentage}%`. Only the JOIN between them was wrong, and neither
 * side's tests could see it: the mapper handed a FRACTION to something expecting
 * a PERCENT.
 *
 * Measured on prod before the fix, on the account with the most items:
 *
 *   pokemon        €79.80   51.6% of portfolio   ->  drew "1%"
 *   one_piece_tcg  €74.80   48.4% of portfolio   ->  drew "0%"
 *
 * ...and every bar collapsed to the `Math.max(pct, 2)` floor, so the chart read
 * as flat and empty while every number behind it was correct.
 */
import { mapCategoryBreakdown } from '@/lib/categoryBreakdown';

describe('mapCategoryBreakdown', () => {
  it('converts the fraction the server sends into a percentage', () => {
    const [row] = mapCategoryBreakdown({
      breakdown: [{ category: 'pokemon', item_count: 3, total_value: 79.8, pct_of_portfolio: 0.5162 }],
    });
    expect(row.percentage).toBeCloseTo(51.62, 2);
  });

  it('reproduces the real prod split, and both halves now read right', () => {
    const rows = mapCategoryBreakdown({
      breakdown: [
        { category: 'pokemon', item_count: 3, total_value: 79.8, pct_of_portfolio: 0.5162 },
        { category: 'one_piece_tcg', item_count: 2, total_value: 74.8, pct_of_portfolio: 0.4838 },
      ],
    });
    // What the section actually prints.
    expect(rows.map((r) => `${r.percentage.toFixed(0)}%`)).toEqual(['52%', '48%']);
    // ...and the shares still add up, which is the point of the chart.
    expect(rows.reduce((n, r) => n + r.percentage, 0)).toBeCloseTo(100, 1);
  });

  it('a whole-portfolio category is 100%, not 1%', () => {
    const [row] = mapCategoryBreakdown({
      breakdown: [{ category: 'lego', item_count: 9, total_value: 150, pct_of_portfolio: 1 }],
    });
    expect(row.percentage).toBe(100);
  });

  it('an unvalued category is 0, not NaN', () => {
    // Real: `uncategorized` and `books` both hold items worth €0.00 on prod.
    const [row] = mapCategoryBreakdown({
      breakdown: [{ category: 'books', item_count: 4, total_value: 0, pct_of_portfolio: 0 }],
    });
    expect(row.percentage).toBe(0);
    expect(row.item_count).toBe(4);
  });

  it('does NOT scale the legacy `percentage` shape, which was already 0–100', () => {
    const [row] = mapCategoryBreakdown({
      breakdown: [{ category: 'comics', item_count: 1, total_value: 10, percentage: 42 }],
    });
    expect(row.percentage).toBe(42);
  });

  it('passes the legacy `categories` array through untouched', () => {
    const rows = mapCategoryBreakdown({
      categories: [{ category: 'watches', item_count: 1, total_value: 500, percentage: 100 }],
    });
    expect(rows[0].percentage).toBe(100);
  });

  it('a failed or empty response is an empty list, never a fabricated row', () => {
    expect(mapCategoryBreakdown(null)).toEqual([]);
    expect(mapCategoryBreakdown({})).toEqual([]);
    expect(mapCategoryBreakdown({ breakdown: [] })).toEqual([]);
  });
});
