/**
 * THE tier vocabulary — one object, two surfaces.
 *
 * docs/ui-playbook.md, "Two boards ranking the same idea should be the same
 * object" (2026-08-17). Until 2026-09-21 there were two `Tier` types with the
 * same name and different members:
 *
 *   src/utils/statusScoring.ts   'Diamond' | 'Gold' | 'Silver'
 *   src/analytics/portfolioMetrics.ts   ...the same three, plus 'Unranked'
 *
 * so a member could read **Gold** on the Items tab and **Unranked** on
 * Analytics for the same collection, in the same session. The type, the floor
 * rule, the colours, the icons and the label keys now live here and nowhere
 * else.
 *
 * ⚠️ THE TWO NUMERIC SCALES ARE STILL DIFFERENT, DELIBERATELY AND VISIBLY.
 * `statusScoring` ranks ONE collection on points out of 100 weighted
 * completeness 60 / rarity 25 / value 15; `portfolioMetrics` ranks the WHOLE
 * portfolio on a composite out of 1 weighted rarity 50 / completeness 30 /
 * diversification 20. Aligning the cut-offs would change what "Gold" means on
 * five shipped screens, which is a product decision, not a refactor. They are
 * declared together here so that decision is made in one place when it is made
 * — rather than rediscovered as a contradiction on screen.
 */

export type Tier = 'Diamond' | 'Gold' | 'Silver' | 'Unranked';

/**
 * Whole-portfolio composite, 0–1 (`portfolioMetrics`).
 *
 * Diamond additionally requires real evidence on the two axes that can be
 * unknown, so a perfectly diversified portfolio of unreadable items cannot
 * reach the top rank on diversification alone.
 */
export const PORTFOLIO_CUTOFFS = {
  diamond: 0.8,
  diamondMinRarity: 0.75,
  diamondMinCompleteness: 0.7,
  gold: 0.55,
  silver: 0.3,
} as const;

/** Single-collection points, 0–100 (`statusScoring`). */
export const COLLECTION_CUTOFFS = {
  diamond: 75,
  gold: 50,
} as const;

export function tierFromComposite(
  composite: number,
  rarity: number,
  completeness: number,
): Tier {
  if (
    composite >= PORTFOLIO_CUTOFFS.diamond &&
    rarity >= PORTFOLIO_CUTOFFS.diamondMinRarity &&
    completeness >= PORTFOLIO_CUTOFFS.diamondMinCompleteness
  ) {
    return 'Diamond';
  }
  if (composite >= PORTFOLIO_CUTOFFS.gold) return 'Gold';
  if (composite >= PORTFOLIO_CUTOFFS.silver) return 'Silver';
  return 'Unranked';
}

/**
 * A ranked collection's tier. Floor is Silver **on purpose**: reaching this
 * function at all means the collection was scored, and `statusScoring` scores
 * every collection a member holds. "Unranked" on this scale would mean
 * something different from what it means on the portfolio scale, and one word
 * cannot mean two things across two screens.
 */
export function tierFromPoints(points: number): Tier {
  if (points >= COLLECTION_CUTOFFS.diamond) return 'Diamond';
  if (points >= COLLECTION_CUTOFFS.gold) return 'Gold';
  return 'Silver';
}

export const TIER_COLORS: Record<Tier, string> = {
  Diamond: '#A78BFA',
  Gold: '#FBBF24',
  Silver: '#94A3B8',
  Unranked: '#64748B',
};

export const TIER_ICONS: Record<Tier, string> = {
  Diamond: 'diamond-outline',
  Gold: 'trophy-outline',
  Silver: 'medal-outline',
  Unranked: 'help-circle-outline',
};

/**
 * i18n key per tier. The tier name used to render as a bare English string on
 * every locale — `{tierSummary.tier}` straight out of the type.
 */
export const TIER_LABEL_KEYS: Record<Tier, string> = {
  Diamond: 'analytics.tier_diamond',
  Gold: 'analytics.tier_gold',
  Silver: 'analytics.tier_silver',
  Unranked: 'analytics.tier_unranked',
};
