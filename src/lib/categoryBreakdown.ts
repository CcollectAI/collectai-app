import type { CategoryBreakdownItem } from '@/components/home/CategoryBreakdownSection';

/**
 * `/analytics/portfolio/category-breakdown` -> what the section renders.
 *
 * ⚠️ THE SERVER SENDS `pct_of_portfolio` AS A FRACTION (0–1), NOT A PERCENT.
 * It computes `round(val / total_value, 4)`, and its own test pins `== 0.625`
 * for a category worth 62.5%. This mapper used to assign it straight across to
 * `percentage`, which `CategoryBreakdownSection` renders BOTH as
 * `percentage.toFixed(0)}%` and as a bar `width: ${percentage}%`.
 *
 * Measured on prod before the fix: pokemon held 51.6% of the portfolio and drew
 * **"1%"**; one_piece_tcg held 48.4% and drew **"0%"**; every bar collapsed to
 * the 2% floor. The chart read as flat and empty while every number behind it
 * was correct.
 *
 * A unit mismatch at a SEAM: the server is self-consistent and tested, the
 * component is self-consistent, and only the join between them was wrong — so
 * no test on either side could see it
 * (learning_verify_the_display_seam_not_isolated_units). Extracted from the
 * loader and exported precisely so that seam now has one.
 *
 * The `categories` / `percentage` shapes are a legacy response that was already
 * 0–100, so the x100 applies ONLY to `pct_of_portfolio`.
 */
export function mapCategoryBreakdown(res: unknown): CategoryBreakdownItem[] {
  const data = (res ?? {}) as Record<string, unknown>;
  if (Array.isArray(data.breakdown)) {
    return (data.breakdown as Record<string, unknown>[]).map((b) => ({
      category: String(b.category ?? ''),
      item_count: Number(b.item_count ?? 0),
      total_value: Number(b.total_value ?? 0),
      percentage: b.pct_of_portfolio != null
        ? Number(b.pct_of_portfolio) * 100
        : Number(b.percentage ?? 0),
    }));
  }
  if (Array.isArray(data.categories)) return data.categories as CategoryBreakdownItem[];
  return [];
}
