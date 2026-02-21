export type CategoryId =
  | 'pokemon'
  | 'mtg'
  | 'yugioh'
  | 'lorcana'
  | 'funko'
  | 'designer_toys'
  | 'anime_figures'
  | 'hot_toys'
  | 'lego'
  | 'gunpla'
  | 'scale_models'
  | 'warhammer'
  | 'retro_games'
  | 'manga'
  | 'bluray_steelbook'
  | 'anime_bluray'
  | 'anime_soundtrack'
  | 'anime_ost_vinyl'
  | 'kpop_merch'
  | 'taylor_swift'
  | 'pop_fandom'
  | 'kpop_lightsticks'
  | 'disney'
  | 'theme_park'
  | 'ghibli'
  | 'bandai_premium'
  | 'jp_magazine'
  | 'jp_event'
  | 'nintendo_merch'
  | 'retro_pokemon'
  | 'one_piece'
  | 'vtuber'
  | 'keycaps'
  | 'loungefly'
  | 'diecast'
  | 'sportscards'
  | 'retro_handhelds';

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
  accentColor: string;
  iconName: string;
  collections: CategoryCollection[];
  externalMarketplaces: ExternalMarketplaceLink[];
  relatedCategoryIds: CategoryId[];
};

/** Accent color + icon lookup by category ID */
export const CATEGORY_VISUAL: Record<CategoryId, { accentColor: string; iconName: string }> = {
  pokemon: { accentColor: '#FFD700', iconName: 'flash' },
  mtg: { accentColor: '#4B0082', iconName: 'flame' },
  yugioh: { accentColor: '#8B4513', iconName: 'triangle' },
  lorcana: { accentColor: '#6A5ACD', iconName: 'sparkles' },
  funko: { accentColor: '#FF6B35', iconName: 'happy' },
  designer_toys: { accentColor: '#E91E63', iconName: 'color-palette' },
  anime_figures: { accentColor: '#FF69B4', iconName: 'body' },
  hot_toys: { accentColor: '#C41E3A', iconName: 'shield' },
  lego: { accentColor: '#FFC107', iconName: 'cube' },
  gunpla: { accentColor: '#1E88E5', iconName: 'rocket' },
  scale_models: { accentColor: '#607D8B', iconName: 'car-sport' },
  warhammer: { accentColor: '#8D0226', iconName: 'skull' },
  retro_games: { accentColor: '#9C27B0', iconName: 'game-controller' },
  manga: { accentColor: '#2196F3', iconName: 'book' },
  bluray_steelbook: { accentColor: '#37474F', iconName: 'disc' },
  anime_bluray: { accentColor: '#00BCD4', iconName: 'film' },
  anime_soundtrack: { accentColor: '#F06292', iconName: 'musical-notes' },
  anime_ost_vinyl: { accentColor: '#AB47BC', iconName: 'vinyl' },
  kpop_merch: { accentColor: '#FF69B4', iconName: 'heart' },
  taylor_swift: { accentColor: '#E040FB', iconName: 'mic' },
  pop_fandom: { accentColor: '#FF7043', iconName: 'star' },
  kpop_lightsticks: { accentColor: '#FFD54F', iconName: 'flashlight' },
  disney: { accentColor: '#1565C0', iconName: 'planet' },
  theme_park: { accentColor: '#4CAF50', iconName: 'ticket' },
  ghibli: { accentColor: '#66BB6A', iconName: 'leaf' },
  bandai_premium: { accentColor: '#E53935', iconName: 'diamond' },
  jp_magazine: { accentColor: '#FF8A65', iconName: 'newspaper' },
  jp_event: { accentColor: '#EF5350', iconName: 'calendar' },
  nintendo_merch: { accentColor: '#E53935', iconName: 'logo-nintendo' },
  retro_pokemon: { accentColor: '#FBC02D', iconName: 'time' },
  one_piece: { accentColor: '#D32F2F', iconName: 'boat' },
  vtuber: { accentColor: '#7C4DFF', iconName: 'videocam' },
  keycaps: { accentColor: '#78909C', iconName: 'keypad' },
  loungefly: { accentColor: '#F48FB1', iconName: 'bag' },
  diecast: { accentColor: '#546E7A', iconName: 'speedometer' },
  sportscards: { accentColor: '#43A047', iconName: 'trophy' },
  retro_handhelds: { accentColor: '#7E57C2', iconName: 'phone-portrait' },
};

export const CATEGORIES: Category[] = [
  {
    id: 'pokemon',
    name: 'Pokémon Cards',
    tagline: 'Modern & vintage Pokémon TCG, tracked like a real portfolio.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1310845/pexels-photo-1310845.jpeg',
    accentColor: '#FFD700',
    iconName: 'flash',
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
    relatedCategoryIds: ['mtg', 'lorcana', 'yugioh', 'retro_pokemon'],
  },
  {
    id: 'mtg',
    name: 'Magic: The Gathering',
    tagline: 'Reserve list, modern staples, and Commander all-stars.',
    bannerImageUrl:
      'https://images.pexels.com/photos/785707/pexels-photo-785707.jpeg',
    accentColor: '#4B0082',
    iconName: 'flame',
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
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['pokemon', 'lorcana', 'yugioh'],
  },
  {
    id: 'yugioh',
    name: 'Yu-Gi-Oh!',
    tagline: 'First editions, ghost rares, and competitive staples.',
    bannerImageUrl:
      'https://images.pexels.com/photos/4507272/pexels-photo-4507272.jpeg',
    accentColor: '#8B4513',
    iconName: 'triangle',
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
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['pokemon', 'mtg', 'lorcana'],
  },
  {
    id: 'lorcana',
    name: 'Disney Lorcana',
    tagline: 'Storyborn, Dreamborn, and Enchanted foils.',
    bannerImageUrl:
      'https://images.pexels.com/photos/4785441/pexels-photo-4785441.jpeg',
    accentColor: '#6A5ACD',
    iconName: 'sparkles',
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
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['pokemon', 'mtg', 'disney'],
  },
  {
    id: 'funko',
    name: 'Funko Pops',
    tagline: 'Vaulted Pops, con exclusives, and chase variants.',
    bannerImageUrl:
      'https://images.pexels.com/photos/5809715/pexels-photo-5809715.jpeg',
    accentColor: '#FF6B35',
    iconName: 'happy',
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
    relatedCategoryIds: ['designer_toys', 'anime_figures', 'disney'],
  },
  {
    id: 'designer_toys',
    name: 'Designer & Art Toys',
    tagline: 'Limited drops, sofubi, and collab runs.',
    bannerImageUrl:
      'https://images.pexels.com/photos/6006941/pexels-photo-6006941.jpeg',
    accentColor: '#E91E63',
    iconName: 'color-palette',
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
    relatedCategoryIds: ['funko', 'anime_figures', 'hot_toys'],
  },
  {
    id: 'anime_figures',
    name: 'Anime Figures',
    tagline: 'Scale figures, nendoroids, and limited edition statues.',
    bannerImageUrl:
      'https://images.pexels.com/photos/7869252/pexels-photo-7869252.jpeg',
    accentColor: '#FF69B4',
    iconName: 'body',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'amiami',
        label: 'AmiAmi',
        url: 'https://www.amiami.com',
      },
    ],
    relatedCategoryIds: ['designer_toys', 'bandai_premium', 'one_piece'],
  },
  {
    id: 'hot_toys',
    name: 'Hot Toys',
    tagline: 'Premium 1/6 scale collectibles from Marvel, Star Wars & more.',
    bannerImageUrl:
      'https://images.pexels.com/photos/163036/mario-luigi-yoschi-figures-163036.jpeg',
    accentColor: '#C41E3A',
    iconName: 'shield',
    collections: [],
    externalMarketplaces: [
      {
        id: 'sideshow',
        label: 'Sideshow',
        url: 'https://www.sideshow.com',
      },
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['anime_figures', 'designer_toys', 'theme_park'],
  },
  {
    id: 'lego',
    name: 'LEGO',
    tagline: 'UCS sets, retired exclusives, and minifigure collections.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1472386/pexels-photo-1472386.jpeg',
    accentColor: '#FFC107',
    iconName: 'cube',
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
    relatedCategoryIds: ['gunpla', 'scale_models', 'disney'],
  },
  {
    id: 'gunpla',
    name: 'Gunpla & Model Kits',
    tagline: 'HG, MG, PG builds tracked like art pieces.',
    bannerImageUrl:
      'https://images.pexels.com/photos/2261169/pexels-photo-2261169.jpeg',
    accentColor: '#1E88E5',
    iconName: 'rocket',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'hlj',
        label: 'HobbyLink Japan',
        url: 'https://www.hlj.com',
      },
    ],
    relatedCategoryIds: ['scale_models', 'warhammer', 'lego'],
  },
  {
    id: 'scale_models',
    name: 'Scale Models',
    tagline: 'Aircraft, tanks, ships, and automotive scale kits.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1409999/pexels-photo-1409999.jpeg',
    accentColor: '#607D8B',
    iconName: 'car-sport',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['gunpla', 'warhammer', 'diecast'],
  },
  {
    id: 'warhammer',
    name: 'Warhammer Minis',
    tagline: 'Painted squads with provenance and pedigree.',
    bannerImageUrl:
      'https://images.pexels.com/photos/106127/pexels-photo-106127.jpeg',
    accentColor: '#8D0226',
    iconName: 'skull',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['gunpla', 'scale_models'],
  },
  {
    id: 'retro_games',
    name: 'Retro Games',
    tagline: 'Sealed classics, graded cartridges, and CIB treasures.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1637438/pexels-photo-1637438.jpeg',
    accentColor: '#9C27B0',
    iconName: 'game-controller',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'pricecharting',
        label: 'PriceCharting',
        url: 'https://www.pricecharting.com',
      },
    ],
    relatedCategoryIds: ['nintendo_merch', 'retro_pokemon', 'sportscards'],
  },
  {
    id: 'manga',
    name: 'Manga',
    tagline: 'First prints, box sets, and out-of-print volumes.',
    bannerImageUrl:
      'https://images.pexels.com/photos/4350099/pexels-photo-4350099.jpeg',
    accentColor: '#2196F3',
    iconName: 'book',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['anime_bluray', 'one_piece', 'jp_magazine'],
  },
  {
    id: 'bluray_steelbook',
    name: 'Blu-ray Steelbooks',
    tagline: 'Limited edition steelbooks and premium releases.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1040160/pexels-photo-1040160.jpeg',
    accentColor: '#37474F',
    iconName: 'disc',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['anime_bluray', 'disney', 'ghibli'],
  },
  {
    id: 'anime_bluray',
    name: 'Anime Blu-rays',
    tagline: 'Limited editions, Japanese imports, and rare box sets.',
    bannerImageUrl:
      'https://images.pexels.com/photos/3945683/pexels-photo-3945683.jpeg',
    accentColor: '#00BCD4',
    iconName: 'film',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'cdjapan',
        label: 'CDJapan',
        url: 'https://www.cdjapan.co.jp',
      },
    ],
    relatedCategoryIds: ['anime_soundtrack', 'manga', 'bluray_steelbook'],
  },
  {
    id: 'anime_soundtrack',
    name: 'Anime Soundtracks',
    tagline: 'Original soundtracks and character song CDs.',
    bannerImageUrl:
      'https://images.pexels.com/photos/164934/pexels-photo-164934.jpeg',
    accentColor: '#F06292',
    iconName: 'musical-notes',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'cdjapan',
        label: 'CDJapan',
        url: 'https://www.cdjapan.co.jp',
      },
    ],
    relatedCategoryIds: ['anime_ost_vinyl', 'anime_bluray', 'kpop_merch'],
  },
  {
    id: 'anime_ost_vinyl',
    name: 'Anime OST Vinyl',
    tagline: 'Limited pressing vinyl soundtracks from classic and modern anime.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1389429/pexels-photo-1389429.jpeg',
    accentColor: '#AB47BC',
    iconName: 'vinyl',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'discogs',
        label: 'Discogs',
        url: 'https://www.discogs.com',
      },
    ],
    relatedCategoryIds: ['anime_soundtrack', 'kpop_merch', 'taylor_swift'],
  },
  {
    id: 'kpop_merch',
    name: 'K-pop Merch',
    tagline: 'Albums, photocards, and official merchandise.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1105666/pexels-photo-1105666.jpeg',
    accentColor: '#FF69B4',
    iconName: 'heart',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['kpop_lightsticks', 'pop_fandom', 'taylor_swift'],
  },
  {
    id: 'taylor_swift',
    name: 'Taylor Swift',
    tagline: 'Limited vinyls, signed editions, and tour exclusives.',
    bannerImageUrl:
      'https://images.pexels.com/photos/167491/pexels-photo-167491.jpeg',
    accentColor: '#E040FB',
    iconName: 'mic',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'discogs',
        label: 'Discogs',
        url: 'https://www.discogs.com',
      },
    ],
    relatedCategoryIds: ['pop_fandom', 'kpop_merch', 'anime_ost_vinyl'],
  },
  {
    id: 'pop_fandom',
    name: 'Pop Fandom',
    tagline: 'Music memorabilia, tour merch, and limited artist drops.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1763075/pexels-photo-1763075.jpeg',
    accentColor: '#FF7043',
    iconName: 'star',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['taylor_swift', 'kpop_merch', 'kpop_lightsticks'],
  },
  {
    id: 'kpop_lightsticks',
    name: 'K-pop Lightsticks',
    tagline: 'Official lightsticks from every generation and group.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1190298/pexels-photo-1190298.jpeg',
    accentColor: '#FFD54F',
    iconName: 'flashlight',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['kpop_merch', 'pop_fandom', 'jp_event'],
  },
  {
    id: 'disney',
    name: 'Disney Collectibles',
    tagline: 'Vintage pins, park exclusives, and limited editions.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1629236/pexels-photo-1629236.jpeg',
    accentColor: '#1565C0',
    iconName: 'planet',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['theme_park', 'ghibli', 'lorcana'],
  },
  {
    id: 'theme_park',
    name: 'Theme Park Collectibles',
    tagline: 'Park exclusives, vintage souvenirs, and limited merch.',
    bannerImageUrl:
      'https://images.pexels.com/photos/2884842/pexels-photo-2884842.jpeg',
    accentColor: '#4CAF50',
    iconName: 'ticket',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['disney', 'ghibli', 'jp_event'],
  },
  {
    id: 'ghibli',
    name: 'Studio Ghibli',
    tagline: 'Official merch, art books, and limited museum exclusives.',
    bannerImageUrl:
      'https://images.pexels.com/photos/7869264/pexels-photo-7869264.jpeg',
    accentColor: '#66BB6A',
    iconName: 'leaf',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['disney', 'anime_bluray', 'theme_park'],
  },
  {
    id: 'bandai_premium',
    name: 'Bandai Premium',
    tagline: 'P-Bandai exclusives, limited kits, and premium releases.',
    bannerImageUrl:
      'https://images.pexels.com/photos/2261169/pexels-photo-2261169.jpeg',
    accentColor: '#E53935',
    iconName: 'diamond',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['gunpla', 'anime_figures', 'jp_event'],
  },
  {
    id: 'jp_magazine',
    name: 'Japanese Magazines',
    tagline: 'Limited edition magazines, mooks, and collector issues.',
    bannerImageUrl:
      'https://images.pexels.com/photos/235985/pexels-photo-235985.jpeg',
    accentColor: '#FF8A65',
    iconName: 'newspaper',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['manga', 'anime_bluray', 'jp_event'],
  },
  {
    id: 'jp_event',
    name: 'Japan Event Exclusives',
    tagline: 'Comiket, Wonder Festival, and event-only items.',
    bannerImageUrl:
      'https://images.pexels.com/photos/2774556/pexels-photo-2774556.jpeg',
    accentColor: '#EF5350',
    iconName: 'calendar',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['bandai_premium', 'anime_figures', 'jp_magazine'],
  },
  {
    id: 'nintendo_merch',
    name: 'Nintendo Merchandise',
    tagline: 'Official Nintendo collectibles, plushies, and exclusives.',
    bannerImageUrl:
      'https://images.pexels.com/photos/371924/pexels-photo-371924.jpeg',
    accentColor: '#E53935',
    iconName: 'logo-nintendo',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['retro_pokemon', 'retro_games', 'pokemon'],
  },
  {
    id: 'retro_pokemon',
    name: 'Retro Pokémon Merchandise',
    tagline: 'Vintage toys, promo items, and classic Pokémon collectibles.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1310845/pexels-photo-1310845.jpeg',
    accentColor: '#FBC02D',
    iconName: 'time',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['pokemon', 'nintendo_merch', 'retro_games'],
  },
  {
    id: 'one_piece',
    name: 'One Piece',
    tagline: 'Figures, manga, and exclusive One Piece collectibles.',
    bannerImageUrl:
      'https://images.pexels.com/photos/7869252/pexels-photo-7869252.jpeg',
    accentColor: '#D32F2F',
    iconName: 'boat',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['anime_figures', 'manga', 'bandai_premium'],
  },
  {
    id: 'vtuber',
    name: 'VTuber Merchandise',
    tagline: 'Hololive, Nijisanji, and indie VTuber official goods.',
    bannerImageUrl:
      'https://images.pexels.com/photos/3945683/pexels-photo-3945683.jpeg',
    accentColor: '#7C4DFF',
    iconName: 'videocam',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['anime_figures', 'kpop_merch', 'jp_event'],
  },
  {
    id: 'keycaps',
    name: 'Custom Keycaps',
    tagline: 'Artisan keycaps, limited group buys, and rare sets.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1772123/pexels-photo-1772123.jpeg',
    accentColor: '#78909C',
    iconName: 'keypad',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'mechmarket',
        label: 'r/mechmarket',
        url: 'https://www.reddit.com/r/mechmarket',
      },
    ],
    relatedCategoryIds: ['designer_toys', 'lego', 'pokemon'],
  },
  {
    id: 'loungefly',
    name: 'Loungefly',
    tagline: 'Limited edition bags, backpacks, and accessories.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1038000/pexels-photo-1038000.jpeg',
    accentColor: '#F48FB1',
    iconName: 'bag',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['disney', 'funko', 'theme_park'],
  },
  {
    id: 'diecast',
    name: 'Diecast & Model Cars',
    tagline: '1:64, 1:24, and premium diecast with real comps.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1409999/pexels-photo-1409999.jpeg',
    accentColor: '#546E7A',
    iconName: 'speedometer',
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
    relatedCategoryIds: ['scale_models', 'gunpla', 'hot_toys'],
  },
  {
    id: 'sportscards',
    name: 'Sports Cards',
    tagline: 'Graded rookies, vintage cards, and investment-grade collectibles.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1111597/pexels-photo-1111597.jpeg',
    accentColor: '#43A047',
    iconName: 'trophy',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'comc',
        label: 'COMC',
        url: 'https://www.comc.com',
      },
    ],
    relatedCategoryIds: ['pokemon', 'retro_games', 'mtg'],
  },
  {
    id: 'retro_handhelds',
    name: 'Retro Handhelds',
    tagline: 'Classic portable gaming hardware from Game Boy to PSP.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1298601/pexels-photo-1298601.jpeg',
    accentColor: '#7E57C2',
    iconName: 'phone-portrait',
    collections: [],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['retro_games', 'nintendo_merch', 'retro_pokemon'],
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
