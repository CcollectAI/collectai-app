/**
 * Which category a low-confidence QuickScan pre-fills on Add manually (2026-09-27).
 *
 * Walk finding: a photo vision could not read came back as
 * `category=nintendo_merch conf=0.00 name=''`, and the hand-off still put
 * "Nintendo Merch" in the form — a zero-confidence guess presented as a
 * pre-fill the member has to notice and undo. A category is carried only when
 * its OWN confidence clears the same bar the scan uses to trust a result.
 */
import { CATEGORY_SLUG_TO_NAME } from '@/constants/categories';

export const HANDOFF_MIN_CATEGORY_CONFIDENCE = 0.3;

export function handoffCategoryName(
  slug: string | null | undefined,
  categoryConfidence: number | null | undefined,
): string | undefined {
  if (!slug) return undefined;
  if ((categoryConfidence ?? 0) < HANDOFF_MIN_CATEGORY_CONFIDENCE) return undefined;
  return CATEGORY_SLUG_TO_NAME[slug];
}
