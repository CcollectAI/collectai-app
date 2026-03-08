/**
 * Edge Classifier — lightweight on-device pre-classification.
 *
 * Provides instant category hints while the server pipeline runs.
 * JS-only, no native modules required.
 *
 * Methods:
 * 1. User context: top categories from their collection (heavily weighted)
 * 2. Image aspect ratio heuristic (portrait=cards, landscape=boxes)
 * 3. Default fallback
 */

export type EdgeClassification = {
  category: string;
  confidence: number;
  method: 'user_context' | 'aspect_ratio' | 'color_hint' | 'default';
};

/** Default category when no signal is available */
const DEFAULT_CATEGORY = 'funko';
const DEFAULT_CONFIDENCE = 0.1;

/** Category distribution from user's collection. */
export type UserCategoryDistribution = Record<string, number>;

/** Image metadata for on-device classification. */
export type ImageMeta = {
  width: number;
  height: number;
  dominantColors?: string[];
};

/**
 * Classify an item on-device based on available signals.
 *
 * Priority:
 * 1. User's top categories (if they predominantly collect one category)
 * 2. Aspect ratio heuristic
 * 3. Default fallback
 */
export function classifyOnDevice(
  imageMeta: ImageMeta | null,
  userCategories: UserCategoryDistribution | null,
): EdgeClassification {
  // Method 1: User context
  if (userCategories) {
    const entries = Object.entries(userCategories).filter(([, count]) => count > 0);
    if (entries.length > 0) {
      entries.sort((a, b) => b[1] - a[1]);
      const [topCat, topCount] = entries[0];
      const totalItems = entries.reduce((sum, [, c]) => sum + c, 0);

      if (totalItems > 0) {
        const dominance = topCount / totalItems;
        if (dominance > 0.4) {
          return {
            category: topCat,
            confidence: Math.min(0.7, dominance * 0.8),
            method: 'user_context',
          };
        }
        if (entries.length >= 2) {
          const top2Dominance = (entries[0][1] + entries[1][1]) / totalItems;
          if (top2Dominance > 0.7) {
            return {
              category: topCat,
              confidence: Math.min(0.5, dominance * 0.6),
              method: 'user_context',
            };
          }
        }
      }
    }
  }

  // Method 2: Aspect ratio heuristic
  if (imageMeta && imageMeta.width > 0 && imageMeta.height > 0) {
    const ratio = imageMeta.width / imageMeta.height;

    // Very portrait (< 0.7): likely a trading card or manga
    if (ratio < 0.7) {
      return { category: 'pokemon', confidence: 0.25, method: 'aspect_ratio' };
    }

    // Very landscape (> 1.5): likely a box set or LEGO box
    if (ratio > 1.5) {
      return { category: 'lego', confidence: 0.2, method: 'aspect_ratio' };
    }

    // Square-ish (0.85-1.15): likely a figure in box or vinyl record
    if (ratio >= 0.85 && ratio <= 1.15) {
      return { category: 'funko', confidence: 0.2, method: 'aspect_ratio' };
    }
  }

  // Method 3: Default fallback
  return {
    category: DEFAULT_CATEGORY,
    confidence: DEFAULT_CONFIDENCE,
    method: 'default',
  };
}

/**
 * Get the user's category distribution from their collection.
 * Call once and cache.
 */
export function buildCategoryDistribution(
  items: Array<{ category: string }>,
): UserCategoryDistribution {
  const dist: UserCategoryDistribution = {};
  for (const item of items) {
    if (item.category) {
      dist[item.category] = (dist[item.category] || 0) + 1;
    }
  }
  return dist;
}
