/**
 * Mock category domain provider.
 */

import type {
  Item,
  CategoryStoreData,
  CategorySummary,
  CategoryMissingItem,
  SpotlightSlide,
  MiniUserProfile,
} from '../types';
import { getCategoryById, CATEGORIES } from '../categories';
import { EVENTS } from '../events';
import { logger } from '@/lib/logger';
import { mockFollowedCategories, ownedCategoryItems } from './mockState';
import * as mockItemsProvider from './mockItemsProvider';

export async function getCategoryStore(categoryId: string): Promise<CategoryStoreData | null> {
  const category = getCategoryById(categoryId);
  if (!category) return null;

  const spotlightSlides: SpotlightSlide[] = [
    {
      id: `${categoryId}-slide-1`,
      title: 'New Releases',
      subtitle: `Fresh ${category.name} drops this week`,
      linkType: 'external',
      linkUrl: category.externalMarketplaces[0]?.url,
    },
    {
      id: `${categoryId}-slide-2`,
      title: 'Top Grails',
      subtitle: 'Most wanted items in the community',
      linkType: 'external',
    },
    {
      id: `${categoryId}-slide-3`,
      title: 'Price Movers',
      subtitle: 'Items trending up this month',
      linkType: 'external',
    },
  ];

  const allItems = await mockItemsProvider.listItems();
  const categoryItems = allItems.filter(
    (item) => item.category.toLowerCase().includes(category.name.toLowerCase().split(' ')[0].toLowerCase())
  );

  const items: Item[] = categoryItems.length > 0 ? categoryItems : [
    {
      id: `${categoryId}-item-1`,
      name: `${category.name} - Rare Find #1`,
      category: category.name,
      price: 450,
    },
    {
      id: `${categoryId}-item-2`,
      name: `${category.name} - Premium Edition`,
      category: category.name,
      price: 890,
    },
    {
      id: `${categoryId}-item-3`,
      name: `${category.name} - Vintage Classic`,
      category: category.name,
      price: 320,
    },
  ];

  const upcomingEvents = EVENTS
    .filter((e) => e.categoryId === categoryId)
    .map((e) => ({
      id: e.id,
      title: e.title,
      kind: e.kind,
      date: e.date,
      time: e.time,
    }));

  const friendsWhoFollow: MiniUserProfile[] = [
    {
      id: 'collector-aurora',
      displayName: 'Aurora',
      avatarColor: '#0ea5e9',
    },
    {
      id: 'collector-rune',
      displayName: 'Rune',
      avatarColor: '#22c55e',
    },
    {
      id: 'collector-mini',
      displayName: 'Mini Martian',
      avatarColor: '#f97316',
    },
  ];

  return {
    categoryId: category.id,
    categoryName: category.name,
    categoryTagline: category.tagline,
    bannerImageUrl: category.bannerImageUrl,
    spotlightSlides,
    items,
    upcomingEvents,
    friendsWhoFollow,
  };
}

export async function listCategorySummaries(): Promise<CategorySummary[]> {
  return CATEGORIES.map((cat, idx) => {
    const totalCount = 50 + idx * 15;
    const pct = Math.min(0.3 + idx * 0.04, 0.95);
    const ownedCount = Math.floor(totalCount * pct);
    const missingCount = totalCount - ownedCount;
    const completionPct = Math.round((ownedCount / totalCount) * 100);

    return {
      id: cat.id,
      name: cat.name,
      completionPct,
      ownedCount,
      missingCount,
      totalCount,
    };
  });
}

export async function listCategoryMissing(categoryId: string): Promise<CategoryMissingItem[]> {
  const category = getCategoryById(categoryId);
  if (!category) return [];

  const mockMissingItems: Record<string, CategoryMissingItem[]> = {
    pokemon: [
      { id: 'pkmn-m1', categoryId, title: 'Charizard VMAX (Rainbow)', brand: 'Pokémon TCG', notes: 'Sword & Shield era grail' },
      { id: 'pkmn-m2', categoryId, title: 'Pikachu Illustrator', brand: 'Pokémon TCG', notes: 'Ultra rare promo' },
      { id: 'pkmn-m3', categoryId, title: 'Base Set 1st Ed Booster Box', brand: 'Pokémon TCG', notes: 'Sealed vintage' },
      { id: 'pkmn-m4', categoryId, title: 'Moonbreon (Alt Art)', brand: 'Pokémon TCG', notes: 'Evolving Skies chase' },
      { id: 'pkmn-m5', categoryId, title: 'Gold Star Umbreon', brand: 'Pokémon TCG', notes: 'POP Series rare' },
      { id: 'pkmn-m6', categoryId, title: 'Shiny Mew VMAX', brand: 'Pokémon TCG', notes: 'Celebrations subset' },
    ],
    funko: [
      { id: 'funko-m1', categoryId, title: 'Metallic Blue Batman #01', brand: 'Funko', notes: 'SDCC 2010 Exclusive' },
      { id: 'funko-m2', categoryId, title: 'Holographic Darth Maul', brand: 'Funko', notes: 'Paris Comic Con' },
      { id: 'funko-m3', categoryId, title: 'Clockwork Orange Alex', brand: 'Funko', notes: 'Vaulted 2013' },
      { id: 'funko-m4', categoryId, title: 'Glow Headless Ned Stark', brand: 'Funko', notes: 'SDCC Exclusive' },
      { id: 'funko-m5', categoryId, title: 'Planet Arlia Vegeta', brand: 'Funko', notes: 'Toy Tokyo grail' },
    ],
    mtg: [
      { id: 'mtg-m1', categoryId, title: 'Black Lotus (Beta)', brand: 'MTG', notes: 'Power Nine' },
      { id: 'mtg-m2', categoryId, title: 'Ancestral Recall (Beta)', brand: 'MTG', notes: 'Power Nine' },
      { id: 'mtg-m3', categoryId, title: 'Underground Sea (Rev)', brand: 'MTG', notes: 'Dual land' },
      { id: 'mtg-m4', categoryId, title: 'Tabernacle at Pendrell Vale', brand: 'MTG', notes: 'Reserved list' },
      { id: 'mtg-m5', categoryId, title: 'Gaea\'s Cradle', brand: 'MTG', notes: 'Commander staple' },
      { id: 'mtg-m6', categoryId, title: 'Mox Diamond', brand: 'MTG', notes: 'Reserved list' },
      { id: 'mtg-m7', categoryId, title: 'Lion\'s Eye Diamond', brand: 'MTG', notes: 'Legacy combo piece' },
    ],
    warhammer: [
      { id: 'wh-m1', categoryId, title: 'Primarch Roboute Guilliman', brand: 'Games Workshop', notes: 'Forge World resin' },
      { id: 'wh-m2', categoryId, title: 'Knight Castellan', brand: 'Games Workshop', notes: 'Imperial Knights' },
      { id: 'wh-m3', categoryId, title: 'Mortarion Daemon Primarch', brand: 'Games Workshop', notes: 'Death Guard centerpiece' },
      { id: 'wh-m4', categoryId, title: 'Warlord Titan', brand: 'Forge World', notes: 'Adeptus Titanicus scale' },
      { id: 'wh-m5', categoryId, title: 'Blood Angels Sanguinor', brand: 'Games Workshop', notes: 'Chapter hero' },
    ],
    designer_toys: [
      { id: 'dt-m1', categoryId, title: 'KAWS Companion (Grey)', brand: 'KAWS', notes: 'Open Edition 2016' },
      { id: 'dt-m2', categoryId, title: 'Bearbrick 1000% Basquiat', brand: 'Medicom', notes: 'Art collab' },
      { id: 'dt-m3', categoryId, title: 'Superplastic Janky', brand: 'Superplastic', notes: 'Artist series' },
      { id: 'dt-m4', categoryId, title: 'Ron English Grin', brand: 'Made by Monsters', notes: 'Limited sofubi' },
      { id: 'dt-m5', categoryId, title: 'Coarse Noop (Cloud)', brand: 'Coarse', notes: 'Colorway exclusive' },
      { id: 'dt-m6', categoryId, title: 'James Jean Azimuth', brand: 'Good Smile', notes: 'First vinyl' },
    ],
  };

  let items: CategoryMissingItem[];
  if (mockMissingItems[categoryId]) {
    items = mockMissingItems[categoryId];
  } else {
    items = Array.from({ length: 8 }, (_, i) => ({
      id: `${categoryId}-missing-${i + 1}`,
      categoryId,
      title: `${category.name} Item #${i + 1}`,
      brand: category.name,
      notes: i % 2 === 0 ? 'Rare variant' : null,
    }));
  }

  return items.filter((item) => !ownedCategoryItems.has(item.id));
}

export async function markCategoryItemOwned(
  categoryItemId: string,
  quantity: number = 1,
  notes?: string,
): Promise<{ success: boolean }> {
  logger.info('[MockDataProvider] markCategoryItemOwned', { categoryItemId, quantity, notes });
  ownedCategoryItems.add(categoryItemId);
  return { success: true };
}

export async function followCategory(categoryId: string): Promise<void> {
  mockFollowedCategories.add(categoryId);
  logger.info('[MockDataProvider] followCategory', { categoryId });
}

export async function unfollowCategory(categoryId: string): Promise<void> {
  mockFollowedCategories.delete(categoryId);
  logger.info('[MockDataProvider] unfollowCategory', { categoryId });
}

export async function listFollowedCategories(): Promise<string[]> {
  return Array.from(mockFollowedCategories);
}

export async function isFollowingCategory(categoryId: string): Promise<boolean> {
  return mockFollowedCategories.has(categoryId);
}

export async function getCategoryDeepDive(_categoryId: string, _days?: number): Promise<Record<string, unknown>> {
  return {
    average_market_price: 0,
    value_distribution: {},
    top_traded_items: [],
    top_movers: [],
  };
}
