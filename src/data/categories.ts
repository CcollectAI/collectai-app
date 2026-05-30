export type CategoryId =
  | 'pokemon'
  | 'mtg'
  | 'yugioh'
  | 'lorcana'
  | 'funko'
  | 'designer_toys'
  | 'anime_figures'
  | 'hot_toys'
  | 'action_figures'
  | 'vintage_toys'
  | 'marvel_legends'
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
  | 'retro_handhelds'
  | 'comic_books'
  | 'vinyl_records'
  | 'digimon'
  | 'one_piece_tcg'
  | 'blind_box'
  | 'whiskey'
  | 'vintage_cameras'
  | 'plush_collectibles'
  | 'pens'
  | 'watches'
  | 'sneakers'
  | 'oop_board_games'
  | 'city_pop_vinyl'
  | 'fragrances';

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
  action_figures: { accentColor: '#1565C0', iconName: 'man' },
  vintage_toys: { accentColor: '#D4A017', iconName: 'time' },
  marvel_legends: { accentColor: '#ED1D24', iconName: 'shield-half' },
  lego: { accentColor: '#FFC107', iconName: 'cube' },
  gunpla: { accentColor: '#1E88E5', iconName: 'rocket' },
  scale_models: { accentColor: '#607D8B', iconName: 'car-sport' },
  warhammer: { accentColor: '#8D0226', iconName: 'skull' },
  retro_games: { accentColor: '#9C27B0', iconName: 'game-controller' },
  manga: { accentColor: '#2196F3', iconName: 'book' },
  bluray_steelbook: { accentColor: '#37474F', iconName: 'disc' },
  anime_bluray: { accentColor: '#00BCD4', iconName: 'film' },
  anime_soundtrack: { accentColor: '#F06292', iconName: 'musical-notes' },
  anime_ost_vinyl: { accentColor: '#AB47BC', iconName: 'disc' },
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
  nintendo_merch: { accentColor: '#E53935', iconName: 'game-controller' },
  retro_pokemon: { accentColor: '#FBC02D', iconName: 'time' },
  one_piece: { accentColor: '#D32F2F', iconName: 'boat' },
  vtuber: { accentColor: '#7C4DFF', iconName: 'videocam' },
  keycaps: { accentColor: '#78909C', iconName: 'keypad' },
  loungefly: { accentColor: '#F48FB1', iconName: 'bag' },
  diecast: { accentColor: '#546E7A', iconName: 'speedometer' },
  sportscards: { accentColor: '#43A047', iconName: 'trophy' },
  retro_handhelds: { accentColor: '#7E57C2', iconName: 'phone-portrait' },
  comic_books: { accentColor: '#E53E3E', iconName: 'book-outline' },
  vinyl_records: { accentColor: '#6B46C1', iconName: 'disc' },
  digimon: { accentColor: '#3B82F6', iconName: 'flash' },
  one_piece_tcg: { accentColor: '#DC2626', iconName: 'boat' },
  blind_box: { accentColor: '#EC4899', iconName: 'gift' },
  whiskey: { accentColor: '#B45309', iconName: 'wine' },
  vintage_cameras: { accentColor: '#78716C', iconName: 'camera' },
  plush_collectibles: { accentColor: '#F472B6', iconName: 'heart-circle' },
  pens: { accentColor: '#065F46', iconName: 'create' },
  watches: { accentColor: '#92400E', iconName: 'watch' },
  sneakers: { accentColor: '#1D4ED8', iconName: 'footsteps' },
  oop_board_games: { accentColor: '#6D4C41', iconName: 'dice' },
  city_pop_vinyl: { accentColor: '#E040FB', iconName: 'musical-note' },
  fragrances: { accentColor: '#CE93D8', iconName: 'rose' },
};

export const CATEGORIES: Category[] = [
  {
    id: 'pokemon',
    name: 'Pokémon Cards',
    tagline: 'Modern & vintage Pokémon TCG, tracked like a real portfolio.',
    bannerImageUrl:
      'https://images.pexels.com/photos/7708408/pexels-photo-7708408.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
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
      'https://images.pexels.com/photos/16321207/pexels-photo-16321207.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#4B0082',
    iconName: 'flame',
    collections: [
      { id: 'mtg-reserve-list', name: 'Reserve List', itemCount: 0 },
      { id: 'mtg-commander-staples', name: 'Commander Staples', itemCount: 0 },
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
    relatedCategoryIds: ['pokemon', 'lorcana', 'yugioh'],
  },
  {
    id: 'yugioh',
    name: 'Yu-Gi-Oh!',
    tagline: 'First editions, ghost rares, and competitive staples.',
    bannerImageUrl:
      'https://images.pexels.com/photos/9661252/pexels-photo-9661252.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#8B4513',
    iconName: 'triangle',
    collections: [
      { id: 'yugioh-ghost-rares', name: 'Ghost Rares', itemCount: 0 },
      { id: 'yugioh-first-editions', name: 'First Editions', itemCount: 0 },
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
    relatedCategoryIds: ['pokemon', 'mtg', 'lorcana'],
  },
  {
    id: 'lorcana',
    name: 'Disney Lorcana',
    tagline: 'Storyborn, Dreamborn, and Enchanted foils.',
    bannerImageUrl:
      'https://images.pexels.com/photos/13321546/pexels-photo-13321546.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#6A5ACD',
    iconName: 'sparkles',
    collections: [
      { id: 'lorcana-enchanted', name: 'Enchanted Cards', itemCount: 0 },
      { id: 'lorcana-promo', name: 'Promo Cards', itemCount: 0 },
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
    relatedCategoryIds: ['pokemon', 'mtg', 'disney'],
  },
  {
    id: 'funko',
    name: 'Funko Pops',
    tagline: 'Vaulted Pops, con exclusives, and chase variants.',
    bannerImageUrl:
      'https://images.pexels.com/photos/4061668/pexels-photo-4061668.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
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
    relatedCategoryIds: ['designer_toys', 'anime_figures', 'action_figures', 'marvel_legends', 'disney'],
  },
  {
    id: 'designer_toys',
    name: 'Designer & Art Toys',
    tagline: 'Limited drops, sofubi, and collab runs.',
    bannerImageUrl:
      'https://images.pexels.com/photos/31872745/pexels-photo-31872745.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#E91E63',
    iconName: 'color-palette',
    collections: [
      { id: 'dt-kaws', name: 'KAWS Companions', itemCount: 0 },
      { id: 'dt-bearbrick', name: 'BE@RBRICK', itemCount: 0 },
    ],
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
      'https://images.pexels.com/photos/15964921/pexels-photo-15964921.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#FF69B4',
    iconName: 'body',
    collections: [
      { id: 'af-nendoroid', name: 'Nendoroid', itemCount: 0 },
      { id: 'af-scale-figures', name: '1/7 Scale Figures', itemCount: 0 },
    ],
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
      {
        id: 'mandarake',
        label: 'Mandarake',
        url: 'https://order.mandarake.co.jp',
      },
    ],
    relatedCategoryIds: ['designer_toys', 'bandai_premium', 'one_piece'],
  },
  {
    id: 'hot_toys',
    name: 'Hot Toys',
    tagline: 'Premium 1/6 scale collectibles from Marvel, Star Wars & more.',
    bannerImageUrl:
      'https://images.pexels.com/photos/17505082/pexels-photo-17505082.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#C41E3A',
    iconName: 'shield',
    collections: [
      { id: 'ht-marvel', name: 'Marvel MMS Series', itemCount: 0 },
      { id: 'ht-star-wars', name: 'Star Wars MMS Series', itemCount: 0 },
    ],
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
    relatedCategoryIds: ['anime_figures', 'designer_toys', 'action_figures', 'marvel_legends'],
  },
  {
    id: 'action_figures',
    name: 'Action Figures',
    tagline: 'From shelf to grail — every line, every wave, every exclusive.',
    bannerImageUrl:
      'https://images.pexels.com/photos/3661193/pexels-photo-3661193.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#1565C0',
    iconName: 'man',
    collections: [
      { id: 'af-star-wars', name: 'Star Wars Black Series', itemCount: 0 },
      { id: 'af-marvel', name: 'Marvel Legends', itemCount: 0 },
    ],
    externalMarketplaces: [
      { id: 'ebay', label: 'eBay', url: 'https://www.ebay.com' },
      { id: 'whatnot', label: 'Whatnot', url: 'https://www.whatnot.com' },
      { id: 'mercari', label: 'Mercari', url: 'https://www.mercari.com' },
    ],
    relatedCategoryIds: ['hot_toys', 'marvel_legends', 'vintage_toys', 'funko'],
  },
  {
    id: 'vintage_toys',
    name: 'Vintage Toys',
    tagline: 'Kenner, Hasbro, and TOMY treasures from the golden age.',
    bannerImageUrl:
      'https://images.pexels.com/photos/3662630/pexels-photo-3662630.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#D4A017',
    iconName: 'time',
    collections: [
      { id: 'vt-star-wars', name: 'Kenner Star Wars', itemCount: 0 },
      { id: 'vt-transformers', name: 'G1 Transformers', itemCount: 0 },
    ],
    externalMarketplaces: [
      { id: 'ebay', label: 'eBay', url: 'https://www.ebay.com' },
      { id: 'whatnot', label: 'Whatnot', url: 'https://www.whatnot.com' },
      { id: 'mercari', label: 'Mercari', url: 'https://www.mercari.com' },
    ],
    relatedCategoryIds: ['action_figures', 'retro_games', 'diecast'],
  },
  {
    id: 'marvel_legends',
    name: 'Marvel Legends',
    tagline: 'Every wave, every BAF, every chase — assemble the collection.',
    bannerImageUrl:
      'https://images.pexels.com/photos/4588065/pexels-photo-4588065.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#ED1D24',
    iconName: 'shield-half',
    collections: [
      { id: 'ml-baf', name: 'Build-A-Figure Waves', itemCount: 0 },
      { id: 'ml-retro', name: 'Retro Carded', itemCount: 0 },
    ],
    externalMarketplaces: [
      { id: 'ebay', label: 'eBay', url: 'https://www.ebay.com' },
      { id: 'whatnot', label: 'Whatnot', url: 'https://www.whatnot.com' },
      { id: 'mercari', label: 'Mercari', url: 'https://www.mercari.com' },
    ],
    relatedCategoryIds: ['action_figures', 'hot_toys', 'funko', 'comic_books'],
  },
  {
    id: 'lego',
    name: 'LEGO',
    tagline: 'UCS sets, retired exclusives, and minifigure collections.',
    bannerImageUrl:
      'https://images.pexels.com/photos/298825/pexels-photo-298825.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
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
      {
        id: 'whatnot',
        label: 'Whatnot',
        url: 'https://www.whatnot.com',
      },
    ],
    relatedCategoryIds: ['gunpla', 'scale_models', 'disney'],
  },
  {
    id: 'gunpla',
    name: 'Gunpla & Model Kits',
    tagline: 'HG, MG, PG builds tracked like art pieces.',
    bannerImageUrl:
      'https://images.pexels.com/photos/185725/pexels-photo-185725.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#1E88E5',
    iconName: 'rocket',
    collections: [
      { id: 'gunpla-mg', name: 'Master Grade', itemCount: 0 },
      { id: 'gunpla-pg', name: 'Perfect Grade', itemCount: 0 },
    ],
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
      {
        id: 'mandarake',
        label: 'Mandarake',
        url: 'https://order.mandarake.co.jp',
      },
    ],
    relatedCategoryIds: ['scale_models', 'warhammer', 'lego'],
  },
  {
    id: 'scale_models',
    name: 'Scale Models',
    tagline: 'Aircraft, tanks, ships, and automotive scale kits.',
    bannerImageUrl:
      'https://images.pexels.com/photos/2249429/pexels-photo-2249429.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#607D8B',
    iconName: 'car-sport',
    collections: [
      { id: 'sm-aircraft', name: '1/48 Aircraft', itemCount: 0 },
      { id: 'sm-armor', name: '1/35 Armor & Tanks', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'scalemates',
        label: 'ScaleMates',
        url: 'https://www.scalemates.com',
      },
    ],
    relatedCategoryIds: ['gunpla', 'warhammer', 'diecast'],
  },
  {
    id: 'warhammer',
    name: 'Warhammer Minis',
    tagline: 'Painted squads with provenance and pedigree.',
    bannerImageUrl:
      'https://images.pexels.com/photos/69378/pexels-photo-69378.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#8D0226',
    iconName: 'skull',
    collections: [
      { id: 'wh-40k', name: 'Warhammer 40K', itemCount: 0 },
      { id: 'wh-aos', name: 'Age of Sigmar', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'games-workshop',
        label: 'Games Workshop',
        url: 'https://www.games-workshop.com',
      },
      {
        id: 'whatnot',
        label: 'Whatnot',
        url: 'https://www.whatnot.com',
      },
    ],
    relatedCategoryIds: ['gunpla', 'scale_models', 'lego'],
  },
  {
    id: 'retro_games',
    name: 'Retro Games',
    tagline: 'Sealed classics, graded cartridges, and CIB treasures.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1373100/pexels-photo-1373100.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#9C27B0',
    iconName: 'game-controller',
    collections: [
      { id: 'rg-nes-snes', name: 'NES & SNES Classics', itemCount: 0 },
      { id: 'rg-n64', name: 'N64 Collection', itemCount: 0 },
      { id: 'rg-backyard-sports', name: 'Backyard Sports', itemCount: 0 },
    ],
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
      {
        id: 'whatnot',
        label: 'Whatnot',
        url: 'https://www.whatnot.com',
      },
    ],
    relatedCategoryIds: ['nintendo_merch', 'retro_pokemon', 'vintage_toys', 'retro_handhelds'],
  },
  {
    id: 'manga',
    name: 'Manga',
    tagline: 'First prints, box sets, and out-of-print volumes.',
    bannerImageUrl:
      'https://images.pexels.com/photos/18848524/pexels-photo-18848524.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#2196F3',
    iconName: 'book',
    collections: [
      { id: 'manga-oop', name: 'Out-of-Print Volumes', itemCount: 0 },
      { id: 'manga-box-sets', name: 'Box Sets', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'mandarake',
        label: 'Mandarake',
        url: 'https://order.mandarake.co.jp',
      },
    ],
    relatedCategoryIds: ['anime_bluray', 'one_piece', 'jp_magazine'],
  },
  {
    id: 'bluray_steelbook',
    name: 'Blu-ray Steelbooks',
    tagline: 'Zavvi exclusives, 4K upgrades, and numbered collector editions.',
    bannerImageUrl:
      'https://images.pexels.com/photos/276005/pexels-photo-276005.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#37474F',
    iconName: 'disc',
    collections: [
      { id: 'sb-4k', name: '4K UHD Steelbooks', itemCount: 0 },
      { id: 'sb-zavvi', name: 'Zavvi Exclusives', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'amazon',
        label: 'Amazon',
        url: 'https://www.amazon.com',
      },
      {
        id: 'discogs',
        label: 'Discogs',
        url: 'https://www.discogs.com',
      },
    ],
    relatedCategoryIds: ['anime_bluray', 'disney', 'ghibli'],
  },
  {
    id: 'anime_bluray',
    name: 'Anime Blu-rays',
    tagline: 'Aniplex exclusives, Japanese imports, and rare box sets worth the hunt.',
    bannerImageUrl:
      'https://images.pexels.com/photos/2249224/pexels-photo-2249224.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#00BCD4',
    iconName: 'film',
    collections: [
      { id: 'ab-aniplex', name: 'Aniplex Limited', itemCount: 0 },
      { id: 'ab-jp-import', name: 'Japanese Imports', itemCount: 0 },
    ],
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
    tagline: 'Hisaishi scores, character song CDs, and first-press OSTs with bonus tracks.',
    bannerImageUrl:
      'https://images.pexels.com/photos/4734714/pexels-photo-4734714.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#F06292',
    iconName: 'musical-notes',
    collections: [
      { id: 'ast-ost', name: 'Original Soundtracks', itemCount: 0 },
      { id: 'ast-character', name: 'Character Song CDs', itemCount: 0 },
    ],
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
    tagline: 'Tiger Lab, Milan Records pressings, and color-splatter anime wax.',
    bannerImageUrl:
      'https://images.pexels.com/photos/164853/pexels-photo-164853.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#AB47BC',
    iconName: 'vinyl',
    collections: [
      { id: 'aov-ghibli', name: 'Ghibli Pressings', itemCount: 0 },
      { id: 'aov-modern', name: 'Modern Anime Vinyl', itemCount: 0 },
    ],
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
    tagline: 'Photocards, signed albums, and Weverse exclusives that sell out in seconds.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1105666/pexels-photo-1105666.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#FF69B4',
    iconName: 'heart',
    collections: [
      { id: 'kpop-photocards', name: 'Photocards', itemCount: 0 },
      { id: 'kpop-signed', name: 'Signed Albums', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'ktown4u',
        label: 'KTown4U',
        url: 'https://www.ktown4u.com',
      },
    ],
    relatedCategoryIds: ['kpop_lightsticks', 'pop_fandom', 'taylor_swift'],
  },
  {
    id: 'taylor_swift',
    name: 'Taylor Swift',
    tagline: 'Signed CDs, Eras Tour exclusives, and colored vinyl variants that define fandom.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1763075/pexels-photo-1763075.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#E040FB',
    iconName: 'mic',
    collections: [
      { id: 'ts-vinyl-variants', name: 'Vinyl Variants', itemCount: 0 },
      { id: 'ts-tour-merch', name: 'Tour Exclusives', itemCount: 0 },
    ],
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
      {
        id: 'stockx',
        label: 'StockX',
        url: 'https://stockx.com',
      },
    ],
    relatedCategoryIds: ['pop_fandom', 'kpop_merch', 'vinyl_records'],
  },
  {
    id: 'pop_fandom',
    name: 'Pop Fandom',
    tagline: 'Concert posters, signed setlists, and limited artist drops that tell a story.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1047442/pexels-photo-1047442.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#FF7043',
    iconName: 'star',
    collections: [
      { id: 'pf-concert-posters', name: 'Concert Posters', itemCount: 0 },
      { id: 'pf-tour-merch', name: 'Tour Merchandise', itemCount: 0 },
    ],
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
      {
        id: 'stockx',
        label: 'StockX',
        url: 'https://stockx.com',
      },
    ],
    relatedCategoryIds: ['taylor_swift', 'kpop_merch', 'vinyl_records'],
  },
  {
    id: 'kpop_lightsticks',
    name: 'K-pop Lightsticks',
    tagline: 'ARMY Bombs, Ocean Sticks, and every gen lightstick that glows in the crowd.',
    bannerImageUrl:
      'https://images.pexels.com/photos/2167381/pexels-photo-2167381.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#FFD54F',
    iconName: 'flashlight',
    collections: [
      { id: 'kl-bts', name: 'BTS ARMY Bombs', itemCount: 0 },
      { id: 'kl-4th-gen', name: '4th Gen Lightsticks', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'ktown4u',
        label: 'KTown4U',
        url: 'https://www.ktown4u.com',
      },
    ],
    relatedCategoryIds: ['kpop_merch', 'pop_fandom', 'jp_event'],
  },
  {
    id: 'disney',
    name: 'Disney Collectibles',
    tagline: 'Pin trading grails, WDCC sculptures, and castle-exclusive merch.',
    bannerImageUrl:
      'https://images.pexels.com/photos/17978912/pexels-photo-17978912.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#1565C0',
    iconName: 'planet',
    collections: [
      { id: 'disney-pins', name: 'Pin Trading Collection', itemCount: 0 },
      { id: 'disney-wdcc', name: 'WDCC Classics', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'shopdisney',
        label: 'shopDisney',
        url: 'https://www.shopdisney.com',
      },
      {
        id: 'mercari',
        label: 'Mercari',
        url: 'https://www.mercari.com',
      },
      {
        id: 'whatnot',
        label: 'Whatnot',
        url: 'https://www.whatnot.com',
      },
    ],
    relatedCategoryIds: ['theme_park', 'ghibli', 'lorcana', 'loungefly', 'funko'],
  },
  {
    id: 'theme_park',
    name: 'Theme Park Collectibles',
    tagline: 'Haunted Mansion memorabilia, vintage pennants, and ride vehicle replicas.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1336429/pexels-photo-1336429.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#4CAF50',
    iconName: 'ticket',
    collections: [
      { id: 'tp-haunted-mansion', name: 'Haunted Mansion', itemCount: 0 },
      { id: 'tp-vintage-souvenirs', name: 'Vintage Souvenirs', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'shopdisney',
        label: 'shopDisney',
        url: 'https://www.shopdisney.com',
      },
      {
        id: 'mercari',
        label: 'Mercari',
        url: 'https://www.mercari.com',
      },
    ],
    relatedCategoryIds: ['disney', 'ghibli', 'jp_event', 'loungefly'],
  },
  {
    id: 'ghibli',
    name: 'Studio Ghibli',
    tagline: 'Museum-exclusive cels, Donguri Republic goods, and Miyazaki art books.',
    bannerImageUrl:
      'https://images.pexels.com/photos/245914/pexels-photo-245914.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#66BB6A',
    iconName: 'leaf',
    collections: [
      { id: 'ghibli-artbooks', name: 'Art Books', itemCount: 0 },
      { id: 'ghibli-museum', name: 'Museum Exclusives', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'mandarake',
        label: 'Mandarake',
        url: 'https://order.mandarake.co.jp',
      },
    ],
    relatedCategoryIds: ['disney', 'anime_bluray', 'theme_park'],
  },
  {
    id: 'bandai_premium',
    name: 'Bandai Premium',
    tagline: 'P-Bandai web-shop exclusives, limited Gundam kits, and SHF reissues.',
    bannerImageUrl:
      'https://images.pexels.com/photos/4502978/pexels-photo-4502978.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#E53935',
    iconName: 'diamond',
    collections: [
      { id: 'bp-gundam', name: 'P-Bandai Gundam', itemCount: 0 },
      { id: 'bp-shf', name: 'S.H.Figuarts Exclusives', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'mandarake',
        label: 'Mandarake',
        url: 'https://order.mandarake.co.jp',
      },
    ],
    relatedCategoryIds: ['gunpla', 'anime_figures', 'jp_event'],
  },
  {
    id: 'jp_magazine',
    name: 'Japanese Magazines',
    tagline: 'Mooks with exclusive figures, vintage issues, and appendix-heavy collector editions.',
    bannerImageUrl:
      'https://images.pexels.com/photos/6664/pexels-photo-6664.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#FF8A65',
    iconName: 'newspaper',
    collections: [
      { id: 'jpm-fashion', name: 'Fashion Mooks', itemCount: 0 },
      { id: 'jpm-anime', name: 'Anime Magazines', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'mandarake',
        label: 'Mandarake',
        url: 'https://order.mandarake.co.jp',
      },
    ],
    relatedCategoryIds: ['manga', 'anime_bluray', 'jp_event'],
  },
  {
    id: 'jp_event',
    name: 'Japan Event Exclusives',
    tagline: 'Comiket circle goods, Wonder Festival garage kits, and event-day-only drops.',
    bannerImageUrl:
      'https://images.pexels.com/photos/29901247/pexels-photo-29901247.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#EF5350',
    iconName: 'calendar',
    collections: [
      { id: 'jpe-comiket', name: 'Comiket Exclusives', itemCount: 0 },
      { id: 'jpe-wonfes', name: 'Wonder Festival', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'mandarake',
        label: 'Mandarake',
        url: 'https://order.mandarake.co.jp',
      },
    ],
    relatedCategoryIds: ['bandai_premium', 'anime_figures', 'jp_magazine'],
  },
  {
    id: 'nintendo_merch',
    name: 'Nintendo Merchandise',
    tagline: 'Amiibo waves, Nintendo Tokyo exclusives, and Club Nintendo relics.',
    bannerImageUrl:
      'https://images.pexels.com/photos/17122728/pexels-photo-17122728.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#E53935',
    iconName: 'logo-nintendo',
    collections: [
      { id: 'nm-amiibo', name: 'Amiibo', itemCount: 0 },
      { id: 'nm-club-nintendo', name: 'Club Nintendo Rewards', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'mercari',
        label: 'Mercari',
        url: 'https://www.mercari.com',
      },
      {
        id: 'pricecharting',
        label: 'PriceCharting',
        url: 'https://www.pricecharting.com/console/amiibo',
      },
      {
        id: 'whatnot',
        label: 'Whatnot',
        url: 'https://www.whatnot.com',
      },
    ],
    relatedCategoryIds: ['retro_pokemon', 'retro_games', 'pokemon', 'plush_collectibles'],
  },
  {
    id: 'retro_pokemon',
    name: 'Retro Pokémon Merchandise',
    tagline: 'TOMY figures, Pokémon Center originals, and 90s promo treasures.',
    bannerImageUrl:
      'https://images.pexels.com/photos/9343494/pexels-photo-9343494.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#FBC02D',
    iconName: 'time',
    collections: [
      { id: 'rp-tomy', name: 'TOMY Figures', itemCount: 0 },
      { id: 'rp-promo', name: 'Vintage Promo Items', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'yahoo-auctions-jp',
        label: 'Yahoo Auctions JP',
        url: 'https://auctions.yahoo.co.jp',
      },
    ],
    relatedCategoryIds: ['pokemon', 'nintendo_merch', 'retro_games'],
  },
  {
    id: 'one_piece',
    name: 'One Piece',
    tagline: 'Portrait of Pirates statues, Ichiban Kuji prizes, and Grand Ship collection kits.',
    bannerImageUrl:
      'https://images.pexels.com/photos/31089960/pexels-photo-31089960.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#D32F2F',
    iconName: 'boat',
    collections: [
      { id: 'op-pop', name: 'Portrait of Pirates', itemCount: 0 },
      { id: 'op-ichiban-kuji', name: 'Ichiban Kuji', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'mandarake',
        label: 'Mandarake',
        url: 'https://order.mandarake.co.jp',
      },
    ],
    relatedCategoryIds: ['anime_figures', 'manga', 'bandai_premium'],
  },
  {
    id: 'vtuber',
    name: 'VTuber Merchandise',
    tagline: 'Hololive birthday merch, Nijisanji voice packs, and Booth.pm indie drops.',
    bannerImageUrl:
      'https://images.pexels.com/photos/29901237/pexels-photo-29901237.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#7C4DFF',
    iconName: 'videocam',
    collections: [
      { id: 'vt-hololive', name: 'Hololive Official', itemCount: 0 },
      { id: 'vt-nijisanji', name: 'Nijisanji Official', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'booth',
        label: 'Booth.pm',
        url: 'https://booth.pm',
      },
    ],
    relatedCategoryIds: ['anime_figures', 'kpop_merch', 'jp_event'],
  },
  {
    id: 'keycaps',
    name: 'Custom Keycaps',
    tagline: 'Jelly Key artisans, GMK group buys, and resin sculpts that turn keyboards into art.',
    bannerImageUrl:
      'https://images.pexels.com/photos/18382824/pexels-photo-18382824.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#78909C',
    iconName: 'keypad',
    collections: [
      { id: 'kc-artisan', name: 'Artisan Keycaps', itemCount: 0 },
      { id: 'kc-gmk', name: 'GMK Sets', itemCount: 0 },
    ],
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
    tagline: 'Convention exclusives, Disney collabs, and vaulted bags that sell for triple.',
    bannerImageUrl:
      'https://images.pexels.com/photos/174662/pexels-photo-174662.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#F48FB1',
    iconName: 'bag',
    collections: [
      { id: 'lf-disney', name: 'Disney Loungefly', itemCount: 0 },
      { id: 'lf-convention', name: 'Convention Exclusives', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'mercari',
        label: 'Mercari',
        url: 'https://www.mercari.com',
      },
      {
        id: 'stockx',
        label: 'StockX',
        url: 'https://stockx.com',
      },
    ],
    relatedCategoryIds: ['disney', 'funko', 'theme_park'],
  },
  {
    id: 'diecast',
    name: 'Diecast & Model Cars',
    tagline: '1:64, 1:24, and premium diecast with real comps.',
    bannerImageUrl:
      'https://images.pexels.com/photos/15679405/pexels-photo-15679405.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#546E7A',
    iconName: 'speedometer',
    collections: [
      {
        id: 'diecast-premium',
        name: 'Premium Lines',
        itemCount: 40,
        totalEstimatedValueEur: 3400,
      },
      {
        id: 'diecast-hot-wheels',
        name: 'Hot Wheels Treasure Hunts',
        itemCount: 0,
      },
    ],
    externalMarketplaces: [
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'amazon',
        label: 'Amazon',
        url: 'https://www.amazon.com',
      },
    ],
    relatedCategoryIds: ['scale_models', 'vintage_toys', 'hot_toys'],
  },
  {
    id: 'sportscards',
    name: 'Sports Cards',
    tagline: 'PSA 10 rookies, vintage Topps, and wax-era investment-grade slabs.',
    bannerImageUrl:
      'https://images.pexels.com/photos/5184684/pexels-photo-5184684.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#43A047',
    iconName: 'trophy',
    collections: [
      { id: 'sc-graded-rookies', name: 'Graded Rookies', itemCount: 0 },
      { id: 'sc-vintage', name: 'Vintage Pre-1980', itemCount: 0 },
    ],
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
      {
        id: 'whatnot',
        label: 'Whatnot',
        url: 'https://www.whatnot.com',
      },
    ],
    relatedCategoryIds: ['pokemon', 'retro_games', 'mtg'],
  },
  {
    id: 'retro_handhelds',
    name: 'Retro Handhelds',
    tagline: 'Boxed Game Boys, modded GBAs, and limited-color PSP editions.',
    bannerImageUrl:
      'https://images.pexels.com/photos/2263816/pexels-photo-2263816.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#7E57C2',
    iconName: 'phone-portrait',
    collections: [
      { id: 'rh-game-boy', name: 'Game Boy Family', itemCount: 0 },
      { id: 'rh-psp', name: 'PSP & PS Vita', itemCount: 0 },
    ],
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
    relatedCategoryIds: ['retro_games', 'nintendo_merch', 'retro_pokemon'],
  },
  {
    id: 'comic_books',
    name: 'Comic Books & Graphic Novels',
    tagline: 'CGC-slabbed key issues, first appearances, and indie gems worth discovering.',
    bannerImageUrl:
      'https://images.pexels.com/photos/20085947/pexels-photo-20085947.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#E53E3E',
    iconName: 'book-outline',
    collections: [
      { id: 'cb-key-issues', name: 'Key Issues', itemCount: 0 },
      { id: 'cb-cgc-slabs', name: 'CGC Graded Slabs', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'comicbookrealm',
        label: 'ComicBookRealm',
        url: 'https://comicbookrealm.com',
      },
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'whatnot',
        label: 'Whatnot',
        url: 'https://www.whatnot.com',
      },
    ],
    relatedCategoryIds: ['manga', 'bluray_steelbook', 'marvel_legends', 'sportscards'],
  },
  {
    id: 'vinyl_records',
    name: 'Vinyl Records',
    tagline: 'OG pressings, limited color splatter runs, and MoFi audiophile gold.',
    bannerImageUrl:
      'https://images.pexels.com/photos/6862361/pexels-photo-6862361.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#6B46C1',
    iconName: 'disc',
    collections: [
      { id: 'vr-first-pressings', name: 'First Pressings', itemCount: 0 },
      { id: 'vr-colored-vinyl', name: 'Colored & Splatter Vinyl', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'discogs',
        label: 'Discogs',
        url: 'https://www.discogs.com',
      },
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['anime_ost_vinyl', 'taylor_swift', 'kpop_merch'],
  },
  {
    id: 'digimon',
    name: 'Digimon TCG',
    tagline: 'Alternate arts, secret rares, and competitive staples.',
    bannerImageUrl:
      'https://images.pexels.com/photos/7708411/pexels-photo-7708411.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#3B82F6',
    iconName: 'flash',
    collections: [
      { id: 'digi-alt-art', name: 'Alternate Arts', itemCount: 0 },
      { id: 'digi-secret-rare', name: 'Secret Rares', itemCount: 0 },
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
    relatedCategoryIds: ['pokemon', 'yugioh', 'one_piece_tcg'],
  },
  {
    id: 'one_piece_tcg',
    name: 'One Piece TCG',
    tagline: 'Leader cards, manga art parallels, and tournament promos.',
    bannerImageUrl:
      'https://images.pexels.com/photos/26891742/pexels-photo-26891742.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#DC2626',
    iconName: 'boat',
    collections: [
      { id: 'optcg-leaders', name: 'Leader Cards', itemCount: 0 },
      { id: 'optcg-manga-art', name: 'Manga Art Parallels', itemCount: 0 },
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
    relatedCategoryIds: ['one_piece', 'pokemon', 'digimon'],
  },
  {
    id: 'blind_box',
    name: 'Blind Box Figures',
    tagline: 'Pop Mart, Sonny Angel, and chase-worthy mystery pulls.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1007533/pexels-photo-1007533.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#EC4899',
    iconName: 'gift',
    collections: [
      { id: 'bb-pop-mart', name: 'Pop Mart Series', itemCount: 0 },
      { id: 'bb-sonny-angel', name: 'Sonny Angel', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'popmart',
        label: 'Pop Mart',
        url: 'https://www.popmart.com',
      },
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
    relatedCategoryIds: ['designer_toys', 'plush_collectibles', 'funko'],
  },
  {
    id: 'whiskey',
    name: 'Whiskey & Spirits',
    tagline: 'Single cask bottlings, allocated bourbons, and Japanese whisky that appreciates like fine art.',
    bannerImageUrl:
      'https://images.pexels.com/photos/5359005/pexels-photo-5359005.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#B45309',
    iconName: 'wine',
    collections: [
      { id: 'wh-scotch', name: 'Scotch Single Malts', itemCount: 0 },
      { id: 'wh-japanese', name: 'Japanese Whisky', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'whiskyauctioneer',
        label: 'Whisky Auctioneer',
        url: 'https://whiskyauctioneer.com',
      },
      {
        id: 'masterofmalt',
        label: 'Master of Malt',
        url: 'https://www.masterofmalt.com',
      },
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['vintage_cameras', 'pens', 'sportscards'],
  },
  {
    id: 'vintage_cameras',
    name: 'Vintage Cameras',
    tagline: 'Leica rangefinders, Hasselblad medium format, and Nikon F bodies built to last forever.',
    bannerImageUrl:
      'https://images.pexels.com/photos/2268843/pexels-photo-2268843.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#78716C',
    iconName: 'camera',
    collections: [
      { id: 'vc-rangefinders', name: 'Rangefinders', itemCount: 0 },
      { id: 'vc-slr', name: 'Film SLRs', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'keh',
        label: 'KEH',
        url: 'https://www.keh.com',
      },
      {
        id: 'mpb',
        label: 'MPB',
        url: 'https://www.mpb.com',
      },
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['pens', 'whiskey', 'diecast'],
  },
  {
    id: 'plush_collectibles',
    name: 'Plush Collectibles',
    tagline: 'Retired Squishmallows, Jellycat bashfuls, and con-exclusive plush that hug back in value.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1860160/pexels-photo-1860160.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#F472B6',
    iconName: 'heart-circle',
    collections: [
      { id: 'pc-squishmallows', name: 'Squishmallows', itemCount: 0 },
      { id: 'pc-jellycat', name: 'Jellycat', itemCount: 0 },
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
      {
        id: 'mercari',
        label: 'Mercari',
        url: 'https://www.mercari.com',
      },
    ],
    relatedCategoryIds: ['blind_box', 'funko', 'nintendo_merch', 'disney'],
  },
  {
    id: 'pens',
    name: 'Fountain Pens & Writing',
    tagline: 'Montblanc limited editions, Pelikan Souverans, and vintage flex nibs worth writing home about.',
    bannerImageUrl:
      'https://images.pexels.com/photos/51326/pexels-photo-51326.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#065F46',
    iconName: 'create',
    collections: [
      { id: 'pens-limited', name: 'Limited Editions', itemCount: 0 },
      { id: 'pens-vintage', name: 'Vintage Pens', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'gouletpens',
        label: 'Goulet Pens',
        url: 'https://www.gouletpens.com',
      },
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['vintage_cameras', 'whiskey', 'diecast'],
  },
  {
    id: 'watches',
    name: 'Watches',
    tagline: 'Rolex sports models, Grand Seiko snowflakes, and vintage chronographs that only gain time.',
    bannerImageUrl:
      'https://images.pexels.com/photos/3490349/pexels-photo-3490349.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#92400E',
    iconName: 'watch',
    collections: [
      { id: 'w-dive', name: 'Dive Watches', itemCount: 0 },
      { id: 'w-dress', name: 'Dress Watches', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'bezel',
        label: 'Bezel',
        url: 'https://www.bezel.com',
      },
      {
        id: 'chrono24',
        label: 'Chrono24',
        url: 'https://www.chrono24.com',
      },
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
    ],
    relatedCategoryIds: ['vintage_cameras', 'pens', 'sneakers'],
  },
  {
    id: 'sneakers',
    name: 'Sneakers & Kicks',
    tagline: 'Off-White collabs, Travis Scott drops, and Jordan OGs that never lose their sole.',
    bannerImageUrl:
      'https://images.pexels.com/photos/19294576/pexels-photo-19294576.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#1D4ED8',
    iconName: 'footsteps',
    collections: [
      { id: 'snk-jordan', name: 'Air Jordan Retros', itemCount: 0 },
      { id: 'snk-collabs', name: 'Designer Collabs', itemCount: 0 },
    ],
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
      {
        id: 'mercari',
        label: 'Mercari',
        url: 'https://www.mercari.com',
      },
    ],
    relatedCategoryIds: ['sportscards', 'watches', 'designer_toys'],
  },
  {
    id: 'oop_board_games',
    name: 'OOP Board Games & KS Exclusives',
    tagline: 'Grail-tier Kickstarters, out-of-print euros, and sealed legacy games that only climb in value.',
    bannerImageUrl:
      'https://images.pexels.com/photos/776654/pexels-photo-776654.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#6D4C41',
    iconName: 'dice',
    collections: [
      { id: 'bg-kickstarter', name: 'Kickstarter Exclusives', itemCount: 0 },
      { id: 'bg-oop-euro', name: 'OOP Euro Classics', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'bgg-market',
        label: 'BGG Market',
        url: 'https://boardgamegeek.com/market',
      },
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'whatnot',
        label: 'Whatnot',
        url: 'https://www.whatnot.com',
      },
    ],
    relatedCategoryIds: ['warhammer', 'retro_games', 'lego'],
  },
  {
    id: 'city_pop_vinyl',
    name: 'City Pop & Future Funk Vinyl',
    tagline: 'OG Japanese pressings, City Pop reissues, and future funk wax from the neon-lit golden age.',
    bannerImageUrl:
      'https://images.pexels.com/photos/1389429/pexels-photo-1389429.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#E040FB',
    iconName: 'musical-note',
    collections: [
      { id: 'cp-og-pressing', name: 'OG Japanese Pressings', itemCount: 0 },
      { id: 'cp-reissues', name: 'Modern Reissues', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'discogs',
        label: 'Discogs',
        url: 'https://www.discogs.com',
      },
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'yahoo-auctions',
        label: 'Yahoo Auctions JP',
        url: 'https://auctions.yahoo.co.jp',
      },
    ],
    relatedCategoryIds: ['vinyl_records', 'anime_ost_vinyl', 'kpop_merch'],
  },
  {
    id: 'fragrances',
    name: 'Fragrances',
    tagline: 'Track your fragrance collection — from designer classics to niche houses worth savoring.',
    bannerImageUrl:
      'https://images.pexels.com/photos/965989/pexels-photo-965989.jpeg?auto=compress&cs=tinysrgb&w=800&h=600&fit=crop',
    accentColor: '#CE93D8',
    iconName: 'rose',
    collections: [
      { id: 'frag-niche', name: 'Niche Houses', itemCount: 0 },
      { id: 'frag-designer', name: 'Designer Fragrances', itemCount: 0 },
      { id: 'frag-indie', name: 'Indie & Artisan', itemCount: 0 },
      { id: 'frag-extrait', name: 'Extrait & Parfum', itemCount: 0 },
    ],
    externalMarketplaces: [
      {
        id: 'fragrantica',
        label: 'Fragrantica',
        url: 'https://www.fragrantica.com',
      },
      {
        id: 'parfumo',
        label: 'Parfumo',
        url: 'https://www.parfumo.com',
      },
      {
        id: 'ebay',
        label: 'eBay',
        url: 'https://www.ebay.com',
      },
      {
        id: 'notino',
        label: 'Notino',
        url: 'https://www.notino.com',
      },
      {
        id: 'fragrancenet',
        label: 'FragranceNet',
        url: 'https://www.fragrancenet.com',
      },
    ],
    relatedCategoryIds: ['whiskey', 'watches', 'pens'],
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

export function getMarketplacesForCategory(catNameOrId: string | null | undefined): ExternalMarketplaceLink[] {
  const fallback: ExternalMarketplaceLink[] = [{ id: 'ebay', label: 'eBay', url: 'https://www.ebay.com' }];
  if (!catNameOrId) return fallback;
  const cat = getCategoryById(catNameOrId as CategoryId) ?? getCategoryByName(catNameOrId);
  return cat?.externalMarketplaces?.length ? cat.externalMarketplaces : fallback;
}

export function getRelatedCategories(category: Category): Category[] {
  return category.relatedCategoryIds
    .map((id) => CATEGORIES.find((c) => c.id === id))
    .filter((c): c is Category => Boolean(c));
}

export const CATEGORY_GROUPS: { label: string; ids: CategoryId[] }[] = [
  { label: 'Trading Card Games', ids: ['pokemon', 'mtg', 'yugioh', 'lorcana', 'digimon', 'one_piece_tcg'] },
  { label: 'Toys & Figures', ids: ['funko', 'designer_toys', 'anime_figures', 'hot_toys', 'action_figures', 'vintage_toys', 'marvel_legends'] },
  { label: 'Building & Models', ids: ['lego', 'gunpla', 'scale_models', 'warhammer'] },
  { label: 'Gaming & Board Games', ids: ['retro_games', 'oop_board_games'] },
  { label: 'Media', ids: ['manga', 'comic_books', 'bluray_steelbook', 'anime_bluray', 'anime_soundtrack', 'anime_ost_vinyl'] },
  { label: 'Music & Fandom', ids: ['kpop_merch', 'taylor_swift', 'pop_fandom', 'kpop_lightsticks'] },
  { label: 'Disney & Theme Parks', ids: ['disney', 'theme_park', 'ghibli'] },
  { label: 'Japan Exclusives', ids: ['bandai_premium', 'jp_magazine', 'jp_event'] },
  { label: 'Nintendo & Pokemon', ids: ['nintendo_merch', 'retro_pokemon'] },
  { label: 'IP-Specific', ids: ['one_piece', 'vtuber'] },
  { label: 'Niche', ids: ['keycaps', 'loungefly'] },
  { label: 'Collectibles', ids: ['blind_box', 'plush_collectibles'] },
  { label: 'Lifestyle', ids: ['vinyl_records', 'city_pop_vinyl', 'sneakers', 'watches'] },
  { label: 'Spirits & Luxury', ids: ['whiskey', 'fragrances', 'vintage_cameras', 'pens'] },
  { label: 'Legacy', ids: ['diecast', 'sportscards', 'retro_handhelds'] },
];

export function getCategoryGroup(id: CategoryId): string | undefined {
  return CATEGORY_GROUPS.find((g) => g.ids.includes(id))?.label;
}
