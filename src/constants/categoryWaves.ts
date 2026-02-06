/**
 * Category wave definitions for the 36-category taxonomy.
 *
 * Source of truth for wave assignments. Derived from the import pipeline
 * tier structure (pipelines/import_all.py) and aligned with
 * src/taxonomy/registry.ts and src/data/categories.ts.
 */

export type CategoryWave = 'wave1' | 'wave2' | 'wave3';

export interface CategoryMeta {
  slug: string;
  label: string;
  wave: CategoryWave;
  active: boolean;
}

// Wave 1: Core categories with rich API data sources
const WAVE1: CategoryMeta[] = [
  { slug: 'pokemon', label: 'Pokemon TCG', wave: 'wave1', active: true },
  { slug: 'mtg', label: 'Magic: The Gathering', wave: 'wave1', active: true },
  { slug: 'yugioh', label: 'Yu-Gi-Oh!', wave: 'wave1', active: true },
  { slug: 'lorcana', label: 'Disney Lorcana', wave: 'wave1', active: true },
  { slug: 'funko', label: 'Funko Pop!', wave: 'wave1', active: true },
  { slug: 'lego', label: 'LEGO', wave: 'wave1', active: true },
  { slug: 'warhammer', label: 'Warhammer', wave: 'wave1', active: true },
  { slug: 'retro_games', label: 'Retro Games', wave: 'wave1', active: true },
  { slug: 'manga', label: 'Manga', wave: 'wave1', active: true },
  { slug: 'sportscards', label: 'Sports Cards', wave: 'wave1', active: true },
];

// Wave 2: Hobby categories with partial API + curated data
const WAVE2: CategoryMeta[] = [
  { slug: 'designer_toys', label: 'Designer Toys', wave: 'wave2', active: true },
  { slug: 'anime_figures', label: 'Anime Figures', wave: 'wave2', active: true },
  { slug: 'hot_toys', label: 'Hot Toys', wave: 'wave2', active: true },
  { slug: 'gunpla', label: 'Gunpla', wave: 'wave2', active: true },
  { slug: 'scale_models', label: 'Scale Models', wave: 'wave2', active: true },
  { slug: 'keycaps', label: 'Artisan Keycaps', wave: 'wave2', active: true },
  { slug: 'bluray_steelbook', label: 'Blu-ray Steelbooks', wave: 'wave2', active: true },
  { slug: 'anime_bluray', label: 'Anime Blu-ray', wave: 'wave2', active: true },
  { slug: 'nintendo_merch', label: 'Nintendo Merch', wave: 'wave2', active: true },
  { slug: 'one_piece', label: 'One Piece', wave: 'wave2', active: true },
  { slug: 'retro_pokemon', label: 'Retro Pokemon', wave: 'wave2', active: true },
  { slug: 'diecast', label: 'Diecast & Hot Wheels', wave: 'wave2', active: true },
];

// Wave 3: Niche categories with curated/manual data
const WAVE3: CategoryMeta[] = [
  { slug: 'kpop_merch', label: 'K-pop Merch', wave: 'wave3', active: true },
  { slug: 'taylor_swift', label: 'Taylor Swift', wave: 'wave3', active: true },
  { slug: 'pop_fandom', label: 'Pop Fandom', wave: 'wave3', active: true },
  { slug: 'kpop_lightsticks', label: 'K-pop Lightsticks', wave: 'wave3', active: true },
  { slug: 'anime_soundtrack', label: 'Anime Soundtracks', wave: 'wave3', active: true },
  { slug: 'anime_ost_vinyl', label: 'Anime OST Vinyl', wave: 'wave3', active: true },
  { slug: 'disney', label: 'Disney Collectibles', wave: 'wave3', active: true },
  { slug: 'theme_park', label: 'Theme Park Exclusives', wave: 'wave3', active: true },
  { slug: 'ghibli', label: 'Studio Ghibli', wave: 'wave3', active: true },
  { slug: 'bandai_premium', label: 'Bandai Premium', wave: 'wave3', active: true },
  { slug: 'vtuber', label: 'VTuber Merch', wave: 'wave3', active: true },
  { slug: 'jp_magazine', label: 'JP Magazine Exclusives', wave: 'wave3', active: true },
  { slug: 'jp_event', label: 'JP Event Exclusives', wave: 'wave3', active: true },
  { slug: 'loungefly', label: 'Loungefly', wave: 'wave3', active: true },
];

export const CATEGORY_WAVES: Record<CategoryWave, CategoryMeta[]> = {
  wave1: WAVE1,
  wave2: WAVE2,
  wave3: WAVE3,
};

export const ALL_CATEGORIES: CategoryMeta[] = [
  ...WAVE1,
  ...WAVE2,
  ...WAVE3,
];

export function getCategoryMeta(slug: string): CategoryMeta | undefined {
  return ALL_CATEGORIES.find((c) => c.slug === slug);
}

export function getActiveCategories(): CategoryMeta[] {
  return ALL_CATEGORIES.filter((c) => c.active);
}

export function getCategoriesByWave(wave: CategoryWave): CategoryMeta[] {
  return CATEGORY_WAVES[wave];
}
