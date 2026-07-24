/**
 * Seam: `/insights/personalized` → screen shapes.
 *
 * Extracted as pure functions on purpose. The previous consumer
 * (`app/(tabs)/marketplace.tsx`) cast the response inline to
 * `{ trending_items?: ... }`, and that cast silently discarded the three
 * other arrays the backend computes — `overexposed_categories`,
 * `diversification_suggestions` and `rare_set_alerts` never reached a screen.
 * An inline `.map()` inside a component is untestable; that is exactly where
 * this class of bug hides (see __tests__/data/screenItem.test.ts).
 *
 * Backend contract — server/app/features/insights_router.py:32-54.
 * NOTE: `share_pct` is a FRACTION (0-1), not a percentage. The backend
 * formats it with `:.0%` (insights_router.py:142), so 0.42 means 42%.
 */

/** Raw wire shape. Every field optional/nullable — this is an untyped `get()`. */
export interface RawPersonalizedInsights {
  overexposed_categories?: { category?: string | null; share_pct?: number | null; risk_level?: string | null }[] | null;
  diversification_suggestions?: (string | null)[] | null;
  rare_set_alerts?: { category?: string | null; item_name?: string | null; note?: string | null }[] | null;
  trending_items?: { category?: string | null; item_name?: string | null; change_pct?: number | null }[] | null;
}

export interface TrendingCategoryShape {
  id: string;
  name: string;
  meta: string;
}

export type RiskLevel = 'high' | 'medium' | 'info';

export interface PortfolioRiskNote {
  /** Stable key for list rendering. */
  id: string;
  text: string;
  level: RiskLevel;
  /** Present only for concentration notes; a fraction 0-1. */
  sharePct?: number;
  category?: string;
}

function normalizeLevel(raw: string | null | undefined): RiskLevel {
  const v = (raw ?? '').toLowerCase();
  if (v === 'high') return 'high';
  if (v === 'medium') return 'medium';
  return 'info';
}

/**
 * Trending categories rail. Unchanged behaviour from the old inline block,
 * moved here so it is covered by the same pass-through test.
 */
export function mapTrendingCategories(
  raw: RawPersonalizedInsights | null | undefined,
  categoryNames: Record<string, string>,
): TrendingCategoryShape[] {
  const items: TrendingCategoryShape[] = [];
  const seen = new Set<string>();
  for (const t of raw?.trending_items ?? []) {
    const category = t?.category;
    if (!category || seen.has(category)) continue;
    seen.add(category);
    const name = categoryNames[category] ?? category;
    const pct = Math.round((t?.change_pct ?? 0) * 100);
    items.push({ id: category, name, meta: pct > 0 ? `+${pct}% this month` : 'Popular' });
  }
  return items;
}

/**
 * Concentration warnings + diversification tips, merged into one ordered list.
 *
 * Ordering is deliberate: concentration risk first (highest level first), then
 * the backend's pre-written suggestion sentences. The suggestion strings are
 * already user-facing prose — do not reformat them here.
 */
export function mapRiskNotes(raw: RawPersonalizedInsights | null | undefined): PortfolioRiskNote[] {
  const notes: PortfolioRiskNote[] = [];

  const exposures = (raw?.overexposed_categories ?? []).filter(
    (e): e is { category: string; share_pct?: number | null; risk_level?: string | null } =>
      !!e && typeof e.category === 'string' && e.category.length > 0,
  );

  const rank: Record<RiskLevel, number> = { high: 0, medium: 1, info: 2 };
  const sorted = [...exposures].sort(
    (a, b) => rank[normalizeLevel(a.risk_level)] - rank[normalizeLevel(b.risk_level)],
  );

  for (const e of sorted) {
    const share = typeof e.share_pct === 'number' ? e.share_pct : undefined;
    const sharePctText = share !== undefined ? `${Math.round(share * 100)}%` : null;
    notes.push({
      id: `exposure:${e.category}`,
      level: normalizeLevel(e.risk_level),
      category: e.category,
      sharePct: share,
      text: sharePctText
        ? `${e.category} is ${sharePctText} of your collection.`
        : `${e.category} is a large share of your collection.`,
    });
  }

  let i = 0;
  for (const s of raw?.diversification_suggestions ?? []) {
    if (typeof s !== 'string' || !s.trim()) continue;
    notes.push({ id: `suggestion:${i++}`, level: 'info', text: s.trim() });
  }

  return notes;
}
