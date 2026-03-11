/**
 * Franchise definitions for cross-category browsing.
 * Each franchise spans multiple categories and matches items via attributesJson keys.
 */
import type { CategoryId } from './categories';

export type Franchise = {
  id: string;
  name: string;
  accentColor: string;
  iconName: string;
  categoryIds: CategoryId[];
  matchKeys: string[];
  matchValues: string[];
};

export const FRANCHISES: Franchise[] = [
  {
    id: 'star_wars',
    name: 'Star Wars',
    accentColor: '#FFE81F',
    iconName: 'planet',
    categoryIds: ['hot_toys', 'action_figures', 'vintage_toys', 'lego', 'funko', 'disney', 'bandai_premium', 'bluray_steelbook'],
    matchKeys: ['franchise', 'theme', 'series', 'license'],
    matchValues: ['star wars', 'mandalorian', 'clone wars', 'the bad batch', 'ahsoka'],
  },
  {
    id: 'marvel',
    name: 'Marvel / MCU',
    accentColor: '#ED1D24',
    iconName: 'shield-half',
    categoryIds: ['hot_toys', 'action_figures', 'marvel_legends', 'funko', 'comic_books', 'disney', 'loungefly', 'lego'],
    matchKeys: ['franchise', 'theme', 'series', 'license', 'publisher'],
    matchValues: ['marvel', 'mcu', 'avengers', 'spider-man', 'x-men', 'deadpool'],
  },
  {
    id: 'dc_comics',
    name: 'DC Comics',
    accentColor: '#0476F2',
    iconName: 'flash',
    categoryIds: ['hot_toys', 'action_figures', 'funko', 'comic_books', 'lego'],
    matchKeys: ['franchise', 'theme', 'series', 'license', 'publisher'],
    matchValues: ['dc', 'batman', 'superman', 'justice league', 'wonder woman'],
  },
  {
    id: 'disney_classic',
    name: 'Disney (Classic)',
    accentColor: '#1565C0',
    iconName: 'planet',
    categoryIds: ['disney', 'funko', 'theme_park', 'loungefly', 'lego', 'plush_collectibles'],
    matchKeys: ['franchise', 'theme', 'license', 'film'],
    matchValues: ['disney', 'pixar', 'frozen', 'lion king', 'little mermaid', 'moana'],
  },
  {
    id: 'pokemon_franchise',
    name: 'Pokemon',
    accentColor: '#FFD700',
    iconName: 'flash',
    categoryIds: ['pokemon', 'retro_pokemon', 'funko', 'nintendo_merch', 'plush_collectibles'],
    matchKeys: ['franchise', 'theme', 'series'],
    matchValues: ['pokemon', 'pikachu', 'pocket monsters'],
  },
  {
    id: 'dragon_ball',
    name: 'Dragon Ball',
    accentColor: '#FF6B00',
    iconName: 'flame',
    categoryIds: ['anime_figures', 'funko', 'bandai_premium', 'manga'],
    matchKeys: ['franchise', 'series', 'anime'],
    matchValues: ['dragon ball', 'dragonball', 'dbz', 'dragon ball super'],
  },
  {
    id: 'one_piece_franchise',
    name: 'One Piece',
    accentColor: '#D32F2F',
    iconName: 'boat',
    categoryIds: ['one_piece', 'one_piece_tcg', 'anime_figures', 'manga', 'bandai_premium'],
    matchKeys: ['franchise', 'series', 'anime'],
    matchValues: ['one piece'],
  },
  {
    id: 'gundam',
    name: 'Gundam',
    accentColor: '#1E88E5',
    iconName: 'rocket',
    categoryIds: ['gunpla', 'bandai_premium', 'anime_figures'],
    matchKeys: ['franchise', 'series'],
    matchValues: ['gundam', 'gunpla', 'mobile suit gundam'],
  },
  {
    id: 'studio_ghibli',
    name: 'Studio Ghibli',
    accentColor: '#66BB6A',
    iconName: 'leaf',
    categoryIds: ['ghibli', 'anime_figures', 'anime_bluray', 'plush_collectibles'],
    matchKeys: ['franchise', 'film', 'studio'],
    matchValues: ['ghibli', 'totoro', 'miyazaki', 'spirited away'],
  },
  {
    id: 'transformers',
    name: 'Transformers',
    accentColor: '#7B2D8B',
    iconName: 'hardware-chip',
    categoryIds: ['vintage_toys', 'action_figures', 'lego'],
    matchKeys: ['franchise', 'series', 'line'],
    matchValues: ['transformers', 'autobots', 'decepticons'],
  },
  {
    id: 'nintendo',
    name: 'Nintendo',
    accentColor: '#E53935',
    iconName: 'game-controller',
    categoryIds: ['nintendo_merch', 'retro_games', 'funko', 'lego', 'plush_collectibles'],
    matchKeys: ['franchise', 'theme', 'platform'],
    matchValues: ['mario', 'zelda', 'nintendo', 'kirby', 'metroid', 'splatoon'],
  },
  {
    id: 'gi_joe',
    name: 'GI Joe',
    accentColor: '#4A6741',
    iconName: 'shield',
    categoryIds: ['vintage_toys', 'action_figures'],
    matchKeys: ['franchise', 'series', 'line'],
    matchValues: ['gi joe', 'g.i. joe', 'cobra', 'classified series'],
  },
  {
    id: 'backyard_sports',
    name: 'Backyard Sports',
    accentColor: '#43A047',
    iconName: 'baseball',
    categoryIds: ['retro_games', 'retro_handhelds'],
    matchKeys: ['franchise', 'series', 'name'],
    matchValues: ['backyard baseball', 'backyard football', 'backyard soccer', 'backyard basketball', 'backyard hockey', 'backyard skateboarding', 'backyard sports', 'humongous entertainment', 'pablo sanchez'],
  },
];

export function getFranchiseById(id: string): Franchise | undefined {
  return FRANCHISES.find((f) => f.id === id);
}

export function getFranchisesForCategory(categoryId: CategoryId): Franchise[] {
  return FRANCHISES.filter((f) => f.categoryIds.includes(categoryId));
}
