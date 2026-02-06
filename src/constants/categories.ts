/**
 * Category display metadata (tint colors + emoji).
 * Source of truth for slugs is src/data/categories.ts — this file adds visual props.
 */

import type { CategoryId } from '@/data/categories';

export type Category = {
  slug: CategoryId;
  name: string;
  tint: string; // hex
  emoji?: string;
};

export const CATEGORIES: Category[] = [
  // Phase 1 — Core (10)
  { slug: 'pokemon', name: 'Pokémon', tint: '#FFCB05', emoji: '⚡' },
  { slug: 'mtg', name: 'Magic: The Gathering', tint: '#B8860B', emoji: '🧙' },
  { slug: 'yugioh', name: 'Yu-Gi-Oh!', tint: '#7B2D8B', emoji: '🃏' },
  { slug: 'lorcana', name: 'Disney Lorcana', tint: '#1E90FF', emoji: '✨' },
  { slug: 'funko', name: 'Funko Pop', tint: '#00B2A9', emoji: '🧸' },
  { slug: 'lego', name: 'LEGO', tint: '#DA291C', emoji: '🧱' },
  { slug: 'warhammer', name: 'Warhammer', tint: '#8B0000', emoji: '⚔️' },
  { slug: 'retro_games', name: 'Retro Games', tint: '#FF6347', emoji: '🕹️' },
  { slug: 'manga', name: 'Manga', tint: '#FF69B4', emoji: '📖' },
  { slug: 'sportscards', name: 'Sports Cards', tint: '#228B22', emoji: '🏈' },

  // Phase 2 — Hobby (12)
  { slug: 'designer_toys', name: 'Designer & Art Toys', tint: '#FF8C00', emoji: '🎨' },
  { slug: 'anime_figures', name: 'Anime Figures', tint: '#E91E8C', emoji: '🎎' },
  { slug: 'hot_toys', name: 'Hot Toys', tint: '#C0392B', emoji: '🦸' },
  { slug: 'gunpla', name: 'Gunpla & Model Kits', tint: '#3498DB', emoji: '🤖' },
  { slug: 'scale_models', name: 'Scale Models', tint: '#7F8C8D', emoji: '✈️' },
  { slug: 'keycaps', name: 'Artisan Keycaps', tint: '#9B59B6', emoji: '⌨️' },
  { slug: 'bluray_steelbook', name: 'Blu-ray Steelbooks', tint: '#2C3E50', emoji: '💿' },
  { slug: 'anime_bluray', name: 'Anime Blu-ray', tint: '#E74C3C', emoji: '📀' },
  { slug: 'nintendo_merch', name: 'Nintendo Merch', tint: '#E60012', emoji: '🍄' },
  { slug: 'one_piece', name: 'One Piece', tint: '#F39C12', emoji: '🏴‍☠️' },
  { slug: 'retro_pokemon', name: 'Retro Pokémon', tint: '#DAA520', emoji: '🔥' },
  { slug: 'diecast', name: 'Diecast & Hot Wheels', tint: '#E67E22', emoji: '🚗' },

  // Phase 3 — Niche (14)
  { slug: 'kpop_merch', name: 'K-pop Merch', tint: '#FF1493', emoji: '🎤' },
  { slug: 'taylor_swift', name: 'Taylor Swift', tint: '#FFD700', emoji: '🎵' },
  { slug: 'pop_fandom', name: 'Pop Fandom', tint: '#FF69B4', emoji: '🌟' },
  { slug: 'kpop_lightsticks', name: 'K-pop Lightsticks', tint: '#BA55D3', emoji: '🔦' },
  { slug: 'anime_soundtrack', name: 'Anime Soundtrack', tint: '#8A2BE2', emoji: '🎶' },
  { slug: 'anime_ost_vinyl', name: 'Anime OST Vinyl', tint: '#4B0082', emoji: '🎧' },
  { slug: 'disney', name: 'Disney', tint: '#1E90FF', emoji: '🏰' },
  { slug: 'theme_park', name: 'Theme Park', tint: '#2ECC71', emoji: '🎢' },
  { slug: 'ghibli', name: 'Studio Ghibli', tint: '#87CEEB', emoji: '🌿' },
  { slug: 'bandai_premium', name: 'Bandai Premium', tint: '#DC143C', emoji: '🎯' },
  { slug: 'jp_magazine', name: 'JP Magazines', tint: '#FF7F50', emoji: '📰' },
  { slug: 'jp_event', name: 'JP Event Exclusives', tint: '#FF4500', emoji: '🎌' },
  { slug: 'vtuber', name: 'VTuber', tint: '#00CED1', emoji: '📺' },
  { slug: 'loungefly', name: 'Loungefly', tint: '#FF1493', emoji: '🎒' },
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
