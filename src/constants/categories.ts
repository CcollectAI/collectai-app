/**
 * Category display metadata (tint colors).
 * Source of truth for slugs is src/data/categories.ts — this file adds visual props.
 */

import type { CategoryId } from '@/data/categories';

export type Category = {
  slug: CategoryId;
  name: string;
  tint: string; // hex
};

export const CATEGORIES: Category[] = [
  // Phase 1 — Core (10)
  { slug: 'pokemon', name: 'Pokémon', tint: '#FFCB05' },
  { slug: 'mtg', name: 'Magic: The Gathering', tint: '#B8860B' },
  { slug: 'yugioh', name: 'Yu-Gi-Oh!', tint: '#7B2D8B' },
  { slug: 'lorcana', name: 'Disney Lorcana', tint: '#1E90FF' },
  { slug: 'funko', name: 'Funko Pop', tint: '#00B2A9' },
  { slug: 'lego', name: 'LEGO', tint: '#DA291C' },
  { slug: 'warhammer', name: 'Warhammer', tint: '#8B0000' },
  { slug: 'retro_games', name: 'Retro Games', tint: '#FF6347' },
  { slug: 'manga', name: 'Manga', tint: '#FF69B4' },
  { slug: 'sportscards', name: 'Sports Cards', tint: '#228B22' },

  // Phase 2 — Hobby (12)
  { slug: 'designer_toys', name: 'Designer & Art Toys', tint: '#FF8C00' },
  { slug: 'anime_figures', name: 'Anime Figures', tint: '#E91E8C' },
  { slug: 'hot_toys', name: 'Hot Toys', tint: '#C0392B' },
  { slug: 'action_figures', name: 'Action Figures', tint: '#1565C0' },
  { slug: 'vintage_toys', name: 'Vintage Toys', tint: '#D4A017' },
  { slug: 'marvel_legends', name: 'Marvel Legends', tint: '#ED1D24' },
  { slug: 'gunpla', name: 'Gunpla & Model Kits', tint: '#3498DB' },
  { slug: 'scale_models', name: 'Scale Models', tint: '#7F8C8D' },
  { slug: 'keycaps', name: 'Artisan Keycaps', tint: '#9B59B6' },
  { slug: 'bluray_steelbook', name: 'Blu-ray Steelbooks', tint: '#2C3E50' },
  { slug: 'anime_bluray', name: 'Anime Blu-ray', tint: '#E74C3C' },
  { slug: 'nintendo_merch', name: 'Nintendo Merch', tint: '#E60012' },
  { slug: 'one_piece', name: 'One Piece', tint: '#F39C12' },
  { slug: 'retro_pokemon', name: 'Retro Pokémon', tint: '#DAA520' },
  { slug: 'diecast', name: 'Diecast & Hot Wheels', tint: '#E67E22' },

  // Phase 3 — Niche (14)
  { slug: 'kpop_merch', name: 'K-pop Merch', tint: '#FF1493' },
  { slug: 'taylor_swift', name: 'Taylor Swift', tint: '#FFD700' },
  { slug: 'pop_fandom', name: 'Pop Fandom', tint: '#FF69B4' },
  { slug: 'kpop_lightsticks', name: 'K-pop Lightsticks', tint: '#BA55D3' },
  { slug: 'anime_soundtrack', name: 'Anime Soundtrack', tint: '#8A2BE2' },
  { slug: 'anime_ost_vinyl', name: 'Anime OST Vinyl', tint: '#4B0082' },
  { slug: 'disney', name: 'Disney', tint: '#1E90FF' },
  { slug: 'theme_park', name: 'Theme Park', tint: '#2ECC71' },
  { slug: 'ghibli', name: 'Studio Ghibli', tint: '#87CEEB' },
  { slug: 'bandai_premium', name: 'Bandai Premium', tint: '#DC143C' },
  { slug: 'jp_magazine', name: 'JP Magazines', tint: '#FF7F50' },
  { slug: 'jp_event', name: 'JP Event Exclusives', tint: '#FF4500' },
  { slug: 'vtuber', name: 'VTuber', tint: '#00CED1' },
  { slug: 'loungefly', name: 'Loungefly', tint: '#FF1493' },

  // Phase 4 — Expansion (12)
  { slug: 'comic_books', name: 'Comic Books', tint: '#E53E3E' },
  { slug: 'vinyl_records', name: 'Vinyl Records', tint: '#6B46C1' },
  { slug: 'digimon', name: 'Digimon TCG', tint: '#3B82F6' },
  { slug: 'one_piece_tcg', name: 'One Piece TCG', tint: '#DC2626' },
  { slug: 'blind_box', name: 'Blind Box Figures', tint: '#EC4899' },
  { slug: 'whiskey', name: 'Whiskey & Spirits', tint: '#B45309' },
  { slug: 'vintage_cameras', name: 'Vintage Cameras', tint: '#78716C' },
  { slug: 'plush_collectibles', name: 'Plush Collectibles', tint: '#F472B6' },
  { slug: 'pens', name: 'Fountain Pens', tint: '#065F46' },
  { slug: 'watches', name: 'Watches', tint: '#92400E' },
  { slug: 'sneakers', name: 'Sneakers', tint: '#1D4ED8' },
  { slug: 'retro_handhelds', name: 'Retro Handhelds', tint: '#7E57C2' },
];

/** Look up a Category by slug */
export function getCategoryBySlug(slug: string): Category | undefined {
  return CATEGORIES.find((c) => c.slug === slug);
}

/** All category display names, sorted */
export function getAllCategoryNames(): string[] {
  return CATEGORIES.map((c) => c.name).sort();
}

/** Map from display name to slug */
export const CATEGORY_NAME_TO_SLUG: Record<string, string> = Object.fromEntries(
  CATEGORIES.map((c) => [c.name, c.slug])
);

/** Map from slug to display name */
export const CATEGORY_SLUG_TO_NAME: Record<string, string> = Object.fromEntries(
  CATEGORIES.map((c) => [c.slug, c.name])
);
