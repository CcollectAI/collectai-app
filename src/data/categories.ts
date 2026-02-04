export type CategoryId =
  | 'pokemon'
  | 'funko'
  | 'diecast'
  | 'mtg'
  | 'lorcana'
  | 'fab'
  | 'warhammer'
  | 'gunpla'
  | 'designer_toys'
  | 'lego';

export type CategoryCollection = {
  id: string;
  name: string;
  itemCount: number;
  totalEstimatedValueEur?: number;
};

export type ExternalMarketplaceLink = {
  id: string;
  label: string;
  icon?: string;
  url: string;
};

export type Category = {
  id: CategoryId;
  name: string;
  tagline: string;
  bannerImageUrl: string;
  collections: CategoryCollection[];
  externalMarketplaces: ExternalMarketplaceLink[];
  relatedCategoryIds: CategoryId[];
};

export const CATEGORIES: Category[] = [
  {
    id: 'pokemon',
    name: 'Pokémon Cards',
    tagline: 'Modern & vintage Pokémon TCG, tracked like a real portfolio.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1310845/pexels-photo-1310845.jpeg',
    collections: [
      {
        id: 'pokemon-modern-grails',
        name: 'Modern Grails',
        itemCount: 24,
        totalEstimatedValueEur: 4800,
      },
      {
        id: 'pokemon-vintage-holo',
        name: 'Vintage Holos',
        itemCount: 18,
        totalEstimatedValueEur: 7200,
      },
    ],
    externalMarketplaces: [
      {
        id: 'cardmarket',
        label: 'Cardmarket',
        url: 'https://www.cardmarket.com',
      },
      {
        id: 'tcgplayer',
        label: 'TCGplayer',
        url: 'https://www.tcgplayer.com',
      },
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['mtg', 'lorcana', 'fab', 'designer_toys'],
  },
  {
    id: 'funko',
    name: 'Funko Pops',
    tagline: 'Vaulted Pops, con exclusives, and chase variants.',
    bannerImageUrl:
      'https://images.pexels.com/photos/5809715/pexels-photo-5809715.jpeg',
    collections: [
      {
        id: 'funko-vaulted',
        name: 'Vaulted Classics',
        itemCount: 32,
        totalEstimatedValueEur: 2600,
      },
      {
        id: 'funko-con-exclusives',
        name: 'Con Exclusives',
        itemCount: 12,
        totalEstimatedValueEur: 1900,
      },
    ],
    externalMarketplaces: [
      {
        id: 'whatnot',
        label: 'Whatnot',
        url: 'https://www.whatnot.com',
      },
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['designer_toys', 'pokemon', 'diecast'],
  },
  {
    id: 'diecast',
    name: 'Diecast & Model Cars',
    tagline: '1:64, 1:24, and premium diecast with real comps.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1409999/pexels-photo-1409999.jpeg',
    collections: [
      {
        id: 'diecast-premium',
        name: 'Premium Lines',
        itemCount: 40,
        totalEstimatedValueEur: 3400,
      },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['gunpla', 'warhammer'],
  },
  {
    id: 'mtg',
    name: 'Magic: The Gathering',
    tagline: 'Reserve list, modern staples, and Commander all-stars.',
    bannerImageUrl:
      'https://images.pexels.com/photos/785707/pexels-photo-785707.jpeg',
    collections: [],
    externalMarketplaces: [
      {
        id: 'cardmarket',
        label: 'Cardmarket',
        url: 'https://www.cardmarket.com',
      },
      {
        id: 'tcgplayer',
        label: 'TCGplayer',
        url: 'https://www.tcgplayer.com',
      },
    ],
    relatedCategoryIds: ['pokemon', 'lorcana', 'fab'],
  },
  {
    id: 'lorcana',
    name: 'Disney Lorcana',
    tagline: 'Storyborn, Dreamborn, and Enchanted foils.',
    bannerImageUrl:
      'https://images.pexels.com/photos/4785441/pexels-photo-4785441.jpeg',
    collections: [],
    externalMarketplaces: [
      {
        id: 'cardmarket',
        label: 'Cardmarket',
        url: 'https://www.cardmarket.com',
      },
    ],
    relatedCategoryIds: ['pokemon', 'mtg'],
  },
  {
    id: 'fab',
    name: 'Flesh and Blood',
    tagline: 'Cold foils, legendaries, and living legend decks.',
    bannerImageUrl:
      'https://images.pexels.com/photos/63478/pexels-photo-63478.jpeg',
    collections: [],
    externalMarketplaces: [
      {
        id: 'tcgplayer',
        label: 'TCGplayer',
        url: 'https://www.tcgplayer.com',
      },
    ],
    relatedCategoryIds: ['mtg', 'pokemon'],
  },
  {
    id: 'warhammer',
    name: 'Warhammer Minis',
    tagline: 'Painted squads with provenance and pedigree.',
    bannerImageUrl:
      'https://images.pexels.com/photos/106127/pexels-photo-106127.jpeg',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['gunpla'],
  },
  {
    id: 'gunpla',
    name: 'Gunpla & Model Kits',
    tagline: 'HG, MG, PG builds tracked like art pieces.',
    bannerImageUrl:
      'https://images.pexels.com/photos/2261169/pexels-photo-2261169.jpeg',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['diecast', 'warhammer'],
  },
  {
    id: 'designer_toys',
    name: 'Designer & Art Toys',
    tagline: 'Limited drops, sofubi, and collab runs.',
    bannerImageUrl:
      'https://images.pexels.com/photos/6006941/pexels-photo-6006941.jpeg',
    collections: [],
    externalMarketplaces: [
      {
        id: 'stockx',
        label: 'StockX',
        url: 'https://stockx.com',
      },
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['funko', 'pokemon'],
  },
  {
    id: 'lego',
    name: 'LEGO',
    tagline: 'UCS sets, retired exclusives, and minifigure collections.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1472386/pexels-photo-1472386.jpeg',
    collections: [
      {
        id: 'lego-ucs',
        name: 'Ultimate Collector Series',
        itemCount: 15,
        totalEstimatedValueEur: 5200,
      },
      {
        id: 'lego-retired',
        name: 'Retired Sets',
        itemCount: 28,
        totalEstimatedValueEur: 3100,
      },
    ],
    externalMarketplaces: [
      {
        id: 'bricklink',
        label: 'BrickLink',
        url: 'https://www.bricklink.com',
      },
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['gunpla', 'diecast'],
  },
];

export function getCategoryById(id: CategoryId | string | null | undefined): Category | undefined {
  if (!id) return undefined;
  return CATEGORIES.find((c) => c.id === id);
}

export function getCategoryByName(name: string | null | undefined): Category | undefined {
  if (!name) return undefined;
  const normalized = name.toLowerCase();
  return CATEGORIES.find(
    (c) => c.name.toLowerCase() === normalized || c.id === normalized
  );
}

export function getRelatedCategories(category: Category): Category[] {
  return category.relatedCategoryIds
    .map((id) => CATEGORIES.find((c) => c.id === id))
    .filter((c): c is Category => Boolean(c));
}
