export type CategoryWave = 'wave1' | 'wave2' | 'wave3';

export interface CategoryMeta {
  slug: string;
  label: string;
  wave: CategoryWave;
  active: boolean;
}

/**
 * Placeholder for the 3-wave / ~30-category taxonomy.
 *
 * The true source of truth is the backend `collectai_categories` table.
 * In a later phase, the app should hydrate this from an API endpoint
 * instead of hardcoding categories here.
 *
 * For now, we keep the structure ready so the UI can start thinking in
 * terms of waves and meta, without locking in a manual list.
 */
export const CATEGORY_WAVES: Record<CategoryWave, CategoryMeta[]> = {
  wave1: [],
  wave2: [],
  wave3: [],
};

export const ALL_CATEGORIES: CategoryMeta[] = [
  // Will be filled from API once we expose a categories endpoint.
];
