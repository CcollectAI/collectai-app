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
import { formatCategoryName } from '@/constants/categories';

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
 * Turn server prose into something written for a person.
 *
 * Two artefacts leak through from the backend's f-strings: category SLUGS in
 * quotes ("your 'lorcana' exposure"), which are column values rather than
 * names, and `--` where an em dash belongs.
 *
 * Conservative by design. A quoted word only changes when it resolves to a
 * category that differs from what was written, so ordinary quoted prose is
 * passed through byte-for-byte rather than being "corrected" into nonsense.
 */
export function humaniseInsight(text: string): string {
  return text
    .replace(/'([a-z0-9_]+)'/g, (whole, slug: string) => {
      const pretty = formatCategoryName(slug);
      return pretty && pretty.toLowerCase() !== slug.toLowerCase() ? pretty : whole;
    })
    .replace(/\s--\s/g, ' \u2014 ');
}

/**
 * Concentration warnings + diversification tips, merged into one ordered list.
 *
 * MERGED, not concatenated. The two arrays describe the SAME fact from two
 * angles, and appending one to the other printed it twice, back to back:
 *
 *   "lorcana is 40% of your collection."
 *   "Your 'lorcana' exposure is 40% of your portfolio. Adding items from other
 *    categories would reduce concentration risk."
 *
 * So each exposure now adopts the server sentence that names it. The server's
 * text wins because it carries the ACTION — ours only restated the number —
 * while the exposure keeps its `level` and `sharePct`, which is why this merges
 * instead of simply dropping our half: the suggestion arrays are all `info`,
 * so discarding the exposure would quietly demote a HIGH concentration warning
 * to a grey informational line.
 *
 * Ordering is unchanged: highest risk first, then unmatched suggestions.
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

  const suggestions = (raw?.diversification_suggestions ?? [])
    .filter((s): s is string => typeof s === 'string' && !!s.trim())
    .map((s) => s.trim());
  /** Indices already spoken for by an exposure, so they are not printed again. */
  const claimed = new Set<number>();

  for (const e of sorted) {
    const share = typeof e.share_pct === 'number' ? e.share_pct : undefined;
    const sharePctText = share !== undefined ? `${Math.round(share * 100)}%` : null;

    const slug = e.category.toLowerCase();
    const matchIdx = suggestions.findIndex(
      (s, i) => !claimed.has(i) && s.toLowerCase().includes(slug),
    );
    if (matchIdx >= 0) claimed.add(matchIdx);

    const name = formatCategoryName(e.category) || e.category;

    notes.push({
      id: `exposure:${e.category}`,
      level: normalizeLevel(e.risk_level),
      category: e.category,
      sharePct: share,
      text:
        matchIdx >= 0
          ? humaniseInsight(suggestions[matchIdx])
          : // No server sentence for this one — say it ourselves, with the
            // DISPLAY name. The screen was printing raw slugs ("lorcana",
            // "mtg"): column values leaking into prose a member reads.
            sharePctText
            ? `${name} is ${sharePctText} of your collection.`
            : `${name} is a large share of your collection.`,
    });
  }

  let i = 0;
  for (const [idx, s] of suggestions.entries()) {
    if (claimed.has(idx)) continue;
    notes.push({ id: `suggestion:${i++}`, level: 'info', text: humaniseInsight(s) });
  }

  return notes;
}
