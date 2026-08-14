/**
 * Versioned Taxonomy Registry
 *
 * Defines category waves (rollout phases) and collection tags.
 * Categories drive schemas/pricing/prefill. Collection tags drive UX grouping.
 *
 * Design:
 * - category_id: canonical category (e.g., 'warhammer')
 * - subtype_id: finer granularity (e.g., 'warhammer_minis' vs 'warhammer_books')
 * - collections: orthogonal tags (e.g., ['taylor_swift', 'eras_tour'])
 */

export const TAXONOMY_VERSION = '2026.02.06';

// ─────────────────────────────────────────────────────────────────────────────
// Category Wave Phases
// ─────────────────────────────────────────────────────────────────────────────

export type CategoryWave = 'phase1' | 'phase2' | 'phase3';

export type CategoryDefinition = {
  id: string;
  name: string;
  wave: CategoryWave;
  subtypes: SubtypeDefinition[];
  keywords?: string[];  // Category-level trigger keywords
  description?: string;
};

export type SubtypeDefinition = {
  id: string;
  name: string;
  keywords: string[];  // For mapping heuristics
  description?: string;
};

// ─────────────────────────────────────────────────────────────────────────────
// Phase 1 Categories (Core TCG + Toys) - 10 categories
// ─────────────────────────────────────────────────────────────────────────────

const PHASE1_CATEGORIES: CategoryDefinition[] = [
  {
    id: 'pokemon',
    name: 'Pokémon TCG',
    wave: 'phase1',
    keywords: ['pokemon', 'pokémon', 'pikachu', 'charizard'],
    subtypes: [
      { id: 'pokemon_cards', name: 'Cards', keywords: ['card', 'holo', 'reverse', 'vmax', 'vstar', 'ex', 'gx'] },
      { id: 'pokemon_sealed', name: 'Sealed Product', keywords: ['booster', 'box', 'etb', 'sealed', 'pack'] },
      { id: 'pokemon_graded', name: 'Graded Cards', keywords: ['psa', 'bgs', 'cgc', 'graded', 'slab'] },
    ],
  },
  {
    id: 'mtg',
    name: 'Magic: The Gathering',
    wave: 'phase1',
    keywords: ['magic', 'mtg', 'gathering', 'wizards of the coast', 'modern horizons', 'commander'],
    subtypes: [
      { id: 'mtg_cards', name: 'Cards', keywords: ['card', 'foil', 'extended', 'borderless'] },
      { id: 'mtg_sealed', name: 'Sealed Product', keywords: ['booster', 'box', 'bundle', 'sealed', 'pack', 'draft'] },
      { id: 'mtg_graded', name: 'Graded Cards', keywords: ['psa', 'bgs', 'cgc', 'graded', 'slab'] },
    ],
  },
  {
    id: 'yugioh',
    name: 'Yu-Gi-Oh!',
    wave: 'phase1',
    keywords: ['yugioh', 'yu-gi-oh', 'ygo'],
    subtypes: [
      { id: 'yugioh_cards', name: 'Cards', keywords: ['card', 'starlight', 'ghost', 'ultimate', 'secret'] },
      { id: 'yugioh_sealed', name: 'Sealed Product', keywords: ['booster', 'box', 'sealed', 'pack', 'tin'] },
      { id: 'yugioh_graded', name: 'Graded Cards', keywords: ['psa', 'bgs', 'cgc', 'graded', 'slab'] },
    ],
  },
  {
    id: 'lorcana',
    name: 'Disney Lorcana',
    wave: 'phase1',
    keywords: ['lorcana', 'disney lorcana'],
    subtypes: [
      { id: 'lorcana_cards', name: 'Cards', keywords: ['card', 'enchanted', 'legendary'] },
      { id: 'lorcana_sealed', name: 'Sealed Product', keywords: ['booster', 'box', 'starter', 'sealed'] },
      { id: 'lorcana_graded', name: 'Graded Cards', keywords: ['psa', 'bgs', 'cgc', 'graded'] },
    ],
  },
  {
    id: 'funko',
    name: 'Funko Pop!',
    wave: 'phase1',
    keywords: ['funko', 'pop', 'vinyl'],
    subtypes: [
      { id: 'funko_pop', name: 'Pop! Vinyl', keywords: ['pop', 'vinyl', 'funko'] },
      { id: 'funko_chase', name: 'Chase Variants', keywords: ['chase', 'variant'] },
      { id: 'funko_exclusive', name: 'Exclusives', keywords: ['exclusive', 'limited', 'sdcc', 'nycc', 'eccc', 'convention'] },
    ],
  },
  {
    id: 'lego',
    name: 'LEGO',
    wave: 'phase1',
    keywords: ['lego'],
    subtypes: [
      { id: 'lego_sealed', name: 'Sealed Sets', keywords: ['sealed', 'nib', 'misb', 'new'] },
      { id: 'lego_retired', name: 'Retired Sets', keywords: ['retired', 'discontinued', 'rare'] },
      { id: 'lego_minifigs', name: 'Minifigures', keywords: ['minifig', 'cmf', 'collectible minifigure'] },
    ],
  },
  {
    id: 'warhammer',
    name: 'Warhammer',
    wave: 'phase1',
    keywords: ['warhammer', '40k', 'age of sigmar', 'games workshop'],
    subtypes: [
      {
        id: 'warhammer_minis',
        name: 'Miniatures',
        keywords: ['mini', 'miniature', 'sprue', 'citadel', '28mm', 'resin', 'assembled', 'painted', 'primed', 'nos', 'nib'],
      },
      {
        id: 'warhammer_books',
        name: 'Books & Codexes',
        keywords: ['codex', 'rulebook', 'battletome', 'black library', 'isbn', 'novel', 'lore'],
      },
      {
        id: 'warhammer_terrain',
        name: 'Terrain & Scenery',
        keywords: ['terrain', 'scenery', 'killzone', 'sector', 'building'],
      },
    ],
  },
  {
    id: 'retro_games',
    name: 'Retro Video Games',
    wave: 'phase1',
    keywords: ['retro', 'vintage', 'classic', 'cib', 'sealed'],
    subtypes: [
      { id: 'retro_games_cib', name: 'Complete in Box', keywords: ['cib', 'complete', 'box', 'manual'] },
      { id: 'retro_games_sealed', name: 'Sealed Games', keywords: ['sealed', 'graded', 'wata', 'vga'] },
      { id: 'retro_games_loose', name: 'Loose Cartridges', keywords: ['loose', 'cartridge', 'cart'] },
      { id: 'retro_games_consoles', name: 'Consoles & Hardware', keywords: ['console', 'system', 'gameboy', 'nes', 'snes', 'n64', 'genesis'] },
    ],
  },
  {
    id: 'manga',
    name: 'Manga',
    wave: 'phase1',
    keywords: ['manga', 'volume', 'vol'],
    subtypes: [
      { id: 'manga_standard', name: 'Standard Edition', keywords: ['standard', 'edition', 'volume'] },
      { id: 'manga_limited', name: 'Limited Edition', keywords: ['limited', 'special', 'deluxe', 'omnibus'] },
      { id: 'manga_oop', name: 'Out of Print', keywords: ['oop', 'out of print', 'rare', 'vintage'] },
    ],
  },
  {
    id: 'sportscards',
    name: 'Sports Cards',
    wave: 'phase1',
    keywords: ['sports', 'trading card', 'rookie'],
    subtypes: [
      { id: 'sportscards_basketball', name: 'Basketball', keywords: ['basketball', 'nba', 'prizm', 'select', 'optic'] },
      { id: 'sportscards_football', name: 'Football', keywords: ['football', 'nfl', 'prizm', 'select', 'optic'] },
      { id: 'sportscards_baseball', name: 'Baseball', keywords: ['baseball', 'mlb', 'topps', 'bowman'] },
      { id: 'sportscards_soccer', name: 'Soccer', keywords: ['soccer', 'football', 'topps', 'panini', 'prizm'] },
    ],
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// Phase 2 Categories (Hobby) - 12 categories
// ─────────────────────────────────────────────────────────────────────────────

const PHASE2_CATEGORIES: CategoryDefinition[] = [
  {
    id: 'designer_toys',
    name: 'Designer Toys',
    wave: 'phase2',
    keywords: ['designer', 'art toy'],
    subtypes: [
      { id: 'designer_kaws', name: 'KAWS', keywords: ['kaws', 'companion', 'medicom'] },
      { id: 'designer_bearbrick', name: 'Be@rbrick', keywords: ['bearbrick', 'be@rbrick', '100%', '400%', '1000%'] },
      { id: 'designer_other', name: 'Other Designer', keywords: ['superplastic', 'coarse', 'mighty jaxx'] },
    ],
  },
  {
    id: 'anime_figures',
    name: 'Anime Figures',
    wave: 'phase2',
    keywords: ['figure', 'anime', 'statue'],
    subtypes: [
      { id: 'anime_figures_nendoroid', name: 'Nendoroid', keywords: ['nendoroid', 'nendo', 'chibi'] },
      { id: 'anime_figures_scale', name: 'Scale Figures', keywords: ['scale', '1/7', '1/8', 'prize', 'kotobukiya'] },
      { id: 'anime_figures_figma', name: 'Figma', keywords: ['figma', 'poseable', 'articulated'] },
    ],
  },
  {
    id: 'hot_toys',
    name: 'Hot Toys',
    wave: 'phase2',
    keywords: ['hot toys', 'sideshow', '1/6'],
    subtypes: [
      { id: 'hot_toys_marvel', name: 'Marvel', keywords: ['marvel', 'iron man', 'spider-man', 'avengers'] },
      { id: 'hot_toys_star_wars', name: 'Star Wars', keywords: ['star wars', 'mandalorian', 'darth vader'] },
      { id: 'hot_toys_dc', name: 'DC', keywords: ['dc', 'batman', 'superman', 'joker'] },
      { id: 'hot_toys_other', name: 'Other Hot Toys', keywords: ['predator', 'alien', 'terminator'] },
    ],
  },
  {
    id: 'dnd',
    name: 'Dungeons & Dragons',
    wave: 'phase2',
    // Deliberately NOT bare 'dice' or 'd20': both appear in Warhammer and board
    // game listings, and a keyword that steals another category's items is
    // worse than one that misses a few (learning_keyword_filters_need_per_
    // category_false_positive_audit).
    keywords: ['dungeons & dragons', 'dungeons and dragons', 'd&d', 'ttrpg', 'tsr'],
    subtypes: [
      { id: 'dnd_rulebook', name: 'Rulebooks', keywords: ['players handbook', 'dungeon master', 'monster manual', 'rulebook'] },
      { id: 'dnd_dice', name: 'Dice Sets', keywords: ['polyhedral', 'dice set', 'd20 set'] },
      { id: 'dnd_minis', name: 'Miniatures', keywords: ['nolzur', 'icons of the realms', 'campaign miniature'] },
    ],
  },
  {
    id: 'gunpla',
    name: 'Gunpla / Model Kits',
    wave: 'phase2',
    keywords: ['gunpla', 'gundam', 'model kit', 'bandai'],
    subtypes: [
      { id: 'gunpla_hg', name: 'High Grade (HG)', keywords: ['hg', 'high grade', '1/144'] },
      { id: 'gunpla_mg', name: 'Master Grade (MG)', keywords: ['mg', 'master grade', '1/100'] },
      { id: 'gunpla_pg', name: 'Perfect Grade (PG)', keywords: ['pg', 'perfect grade', '1/60'] },
      { id: 'gunpla_rg', name: 'Real Grade (RG)', keywords: ['rg', 'real grade'] },
    ],
  },
  {
    id: 'scale_models',
    name: 'Scale Models',
    wave: 'phase2',
    keywords: ['scale model', 'tamiya', 'revell'],
    subtypes: [
      { id: 'scale_models_aircraft', name: 'Aircraft', keywords: ['aircraft', 'plane', '1/48', '1/72'] },
      { id: 'scale_models_armor', name: 'Armor & Tanks', keywords: ['tank', 'armor', 'afv', '1/35'] },
      { id: 'scale_models_automotive', name: 'Automotive', keywords: ['car', 'auto', '1/24', '1/12'] },
    ],
  },
  {
    id: 'keycaps',
    name: 'Artisan Keycaps',
    wave: 'phase2',
    keywords: ['keycap', 'artisan', 'mechanical keyboard'],
    subtypes: [
      { id: 'keycaps_artisan', name: 'Artisan', keywords: ['artisan', 'sculpt', 'resin'] },
      { id: 'keycaps_gmk', name: 'GMK Sets', keywords: ['gmk', 'keyset', 'doubleshot'] },
      { id: 'keycaps_gb', name: 'Group Buy', keywords: ['group buy', 'gb', 'limited run'] },
    ],
  },
  {
    id: 'bluray_steelbook',
    name: 'Blu-ray Steelbooks',
    wave: 'phase2',
    keywords: ['steelbook', 'bluray', 'blu-ray', '4k'],
    subtypes: [
      { id: 'bluray_steelbook_standard', name: 'Steelbook', keywords: ['steelbook', 'steel'] },
      { id: 'bluray_steelbook_4k', name: '4K UHD', keywords: ['4k', 'uhd', 'ultra hd'] },
      { id: 'bluray_steelbook_criterion', name: 'Criterion', keywords: ['criterion', 'collection'] },
    ],
  },
  {
    id: 'anime_bluray',
    name: 'Anime Blu-ray',
    wave: 'phase2',
    keywords: ['anime', 'bluray', 'blu-ray', 'dvd'],
    subtypes: [
      { id: 'anime_bluray_limited', name: 'Limited Edition', keywords: ['limited', 'special', 'box set'] },
      { id: 'anime_bluray_standard', name: 'Standard Edition', keywords: ['standard', 'edition'] },
      { id: 'anime_bluray_import', name: 'Import', keywords: ['import', 'japan', 'region'] },
    ],
  },
  {
    id: 'nintendo_merch',
    name: 'Nintendo Merchandise',
    wave: 'phase2',
    keywords: ['nintendo', 'mario', 'zelda', 'pokemon'],
    subtypes: [
      { id: 'nintendo_merch_plush', name: 'Plush', keywords: ['plush', 'plushie', 'sanei'] },
      { id: 'nintendo_merch_figures', name: 'Figures', keywords: ['figure', 'amiibo', 'world of nintendo'] },
      { id: 'nintendo_merch_collectibles', name: 'Collectibles', keywords: ['collectible', 'merch', 'official'] },
    ],
  },
  {
    id: 'one_piece',
    name: 'One Piece',
    wave: 'phase2',
    keywords: ['one piece', 'luffy', 'straw hat'],
    subtypes: [
      { id: 'one_piece_figures', name: 'Figures', keywords: ['figure', 'figuarts', 'portrait of pirates'] },
      { id: 'one_piece_cards', name: 'TCG', keywords: ['card', 'tcg', 'booster'] },
      { id: 'one_piece_manga', name: 'Manga', keywords: ['manga', 'volume', 'omnibus'] },
    ],
  },
  {
    id: 'retro_pokemon',
    name: 'Retro Pokémon',
    wave: 'phase2',
    keywords: ['retro', 'vintage', 'pokemon', 'pokémon'],
    subtypes: [
      { id: 'retro_pokemon_base', name: 'Base Set Era', keywords: ['base set', 'jungle', 'fossil', 'wizards'] },
      { id: 'retro_pokemon_neo', name: 'Neo Era', keywords: ['neo', 'genesis', 'discovery', 'revelation'] },
      { id: 'retro_pokemon_ex', name: 'EX Era', keywords: ['ex', 'holon', 'rocket', 'delta species'] },
    ],
  },
  {
    id: 'diecast',
    name: 'Diecast & Hot Wheels',
    wave: 'phase2',
    keywords: ['diecast', 'hot wheels', 'matchbox'],
    subtypes: [
      { id: 'diecast_hotwheels', name: 'Hot Wheels', keywords: ['hot wheels', 'hotwheels', 'mainline', 'th', 'sth'] },
      { id: 'diecast_matchbox', name: 'Matchbox', keywords: ['matchbox'] },
      { id: 'diecast_premium', name: 'Premium Diecast', keywords: ['autoart', 'minichamps', 'spark', '1:18', '1:43'] },
    ],
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// Phase 3 Categories (Niche) - 14 categories
// ─────────────────────────────────────────────────────────────────────────────

const PHASE3_CATEGORIES: CategoryDefinition[] = [
  {
    id: 'kpop_merch',
    name: 'K-pop Merchandise',
    wave: 'phase3',
    keywords: ['kpop', 'k-pop', 'korean pop'],
    subtypes: [
      { id: 'kpop_merch_photocard', name: 'Photocards', keywords: ['photocard', 'pc', 'photo card', 'pob'] },
      { id: 'kpop_merch_album', name: 'Albums', keywords: ['album', 'cd', 'signed'] },
      { id: 'kpop_merch_official', name: 'Official Merch', keywords: ['merch', 'official', 'tour', 'concert'] },
    ],
  },
  {
    id: 'taylor_swift',
    name: 'Taylor Swift',
    wave: 'phase3',
    keywords: ['taylor swift', 'swiftie', 'eras tour'],
    subtypes: [
      { id: 'taylor_swift_vinyl', name: 'Vinyl', keywords: ['vinyl', 'record', 'lp', 'colored'] },
      { id: 'taylor_swift_signed', name: 'Signed Items', keywords: ['signed', 'autograph', 'autographed'] },
      { id: 'taylor_swift_merch', name: 'Merchandise', keywords: ['merch', 'tour', 'eras', 'official'] },
    ],
  },
  {
    id: 'pop_fandom',
    name: 'Pop Fandom',
    wave: 'phase3',
    keywords: ['fandom', 'pop culture', 'fan'],
    subtypes: [
      { id: 'pop_fandom_posters', name: 'Posters & Prints', keywords: ['poster', 'print', 'art'] },
      { id: 'pop_fandom_pins', name: 'Pins & Badges', keywords: ['pin', 'badge', 'enamel'] },
      { id: 'pop_fandom_misc', name: 'Misc Collectibles', keywords: ['collectible', 'merch', 'fan made'] },
    ],
  },
  {
    id: 'kpop_lightsticks',
    name: 'K-pop Lightsticks',
    wave: 'phase3',
    keywords: ['lightstick', 'light stick', 'official'],
    subtypes: [
      { id: 'kpop_lightsticks_official', name: 'Official Lightsticks', keywords: ['official', 'lightstick', 'army bomb', 'bong'] },
      { id: 'kpop_lightsticks_limited', name: 'Limited Edition', keywords: ['limited', 'special', 'tour'] },
    ],
  },
  {
    id: 'anime_soundtrack',
    name: 'Anime Soundtracks',
    wave: 'phase3',
    keywords: ['anime', 'soundtrack', 'ost', 'cd'],
    subtypes: [
      { id: 'anime_soundtrack_cd', name: 'CD', keywords: ['cd', 'disc', 'soundtrack'] },
      { id: 'anime_soundtrack_limited', name: 'Limited Edition', keywords: ['limited', 'special', 'bonus'] },
    ],
  },
  {
    id: 'anime_ost_vinyl',
    name: 'Anime OST Vinyl',
    wave: 'phase3',
    keywords: ['anime', 'ost', 'vinyl', 'soundtrack'],
    subtypes: [
      { id: 'anime_ost_vinyl_standard', name: 'Standard Pressing', keywords: ['vinyl', 'lp', 'record'] },
      { id: 'anime_ost_vinyl_limited', name: 'Limited Pressing', keywords: ['limited', 'colored', 'numbered'] },
    ],
  },
  {
    id: 'disney',
    name: 'Disney Collectibles',
    wave: 'phase3',
    keywords: ['disney', 'mickey', 'minnie'],
    subtypes: [
      { id: 'disney_pins', name: 'Trading Pins', keywords: ['pin', 'trading', 'enamel', 'LE'] },
      { id: 'disney_figures', name: 'Figures', keywords: ['figure', 'statue', 'showcase'] },
      { id: 'disney_ears', name: 'Ears & Headbands', keywords: ['ears', 'headband', 'minnie ears'] },
    ],
  },
  {
    id: 'theme_park',
    name: 'Theme Park Merch',
    wave: 'phase3',
    keywords: ['theme park', 'disneyland', 'disney world', 'universal'],
    subtypes: [
      { id: 'theme_park_exclusive', name: 'Park Exclusives', keywords: ['exclusive', 'park', 'limited'] },
      { id: 'theme_park_popcorn', name: 'Popcorn Buckets', keywords: ['popcorn', 'bucket', 'souvenir'] },
      { id: 'theme_park_misc', name: 'Misc Merch', keywords: ['merch', 'souvenir', 'collectible'] },
    ],
  },
  {
    id: 'ghibli',
    name: 'Studio Ghibli',
    wave: 'phase3',
    keywords: ['ghibli', 'totoro', 'spirited away', 'miyazaki'],
    subtypes: [
      { id: 'ghibli_figures', name: 'Figures', keywords: ['figure', 'statue', 'nendoroid'] },
      { id: 'ghibli_plush', name: 'Plush', keywords: ['plush', 'plushie', 'totoro'] },
      { id: 'ghibli_misc', name: 'Misc Collectibles', keywords: ['collectible', 'merch', 'art'] },
    ],
  },
  {
    id: 'bandai_premium',
    name: 'Bandai Premium',
    wave: 'phase3',
    keywords: ['bandai', 'premium', 'p-bandai', 'pbandai'],
    subtypes: [
      { id: 'bandai_premium_gunpla', name: 'P-Bandai Gunpla', keywords: ['gunpla', 'mg', 'hg', 'rg'] },
      { id: 'bandai_premium_figures', name: 'P-Bandai Figures', keywords: ['figure', 'figuarts', 'shf'] },
      { id: 'bandai_premium_misc', name: 'Other P-Bandai', keywords: ['premium', 'exclusive', 'limited'] },
    ],
  },
  {
    id: 'vtuber',
    name: 'VTuber Merch',
    wave: 'phase3',
    keywords: ['vtuber', 'hololive', 'nijisanji', 'virtual youtuber'],
    subtypes: [
      { id: 'vtuber_acrylic', name: 'Acrylic Stands', keywords: ['acrylic', 'stand', 'standee'] },
      { id: 'vtuber_merch', name: 'Official Merch', keywords: ['merch', 'official', 'goods'] },
      { id: 'vtuber_voice', name: 'Voice Packs', keywords: ['voice', 'pack', 'audio', 'cd'] },
    ],
  },
  {
    id: 'jp_magazine',
    name: 'Japanese Magazines',
    wave: 'phase3',
    keywords: ['magazine', 'japanese', 'dengeki', 'famitsu'],
    subtypes: [
      { id: 'jp_magazine_dengeki', name: 'Dengeki', keywords: ['dengeki', 'hobby'] },
      { id: 'jp_magazine_famitsu', name: 'Famitsu', keywords: ['famitsu', 'gaming'] },
      { id: 'jp_magazine_other', name: 'Other Magazines', keywords: ['magazine', 'import', 'japanese'] },
    ],
  },
  {
    id: 'jp_event',
    name: 'Japanese Event Items',
    wave: 'phase3',
    keywords: ['event', 'japan', 'exclusive'],
    subtypes: [
      { id: 'jp_event_wonfes', name: 'WonFes Exclusives', keywords: ['wonfes', 'wonder festival', 'exclusive'] },
      { id: 'jp_event_comiket', name: 'Comiket Items', keywords: ['comiket', 'c99', 'c100', 'doujin'] },
      { id: 'jp_event_other', name: 'Other Events', keywords: ['event', 'exclusive', 'limited'] },
    ],
  },
  {
    id: 'loungefly',
    name: 'Loungefly',
    wave: 'phase3',
    keywords: ['loungefly', 'bag', 'backpack'],
    subtypes: [
      { id: 'loungefly_bags', name: 'Mini Backpacks', keywords: ['backpack', 'mini', 'bag'] },
      { id: 'loungefly_wallets', name: 'Wallets', keywords: ['wallet', 'cardholder'] },
      { id: 'loungefly_crossbody', name: 'Crossbody Bags', keywords: ['crossbody', 'purse', 'bag'] },
    ],
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// Collection Tags (Orthogonal to Categories)
// ─────────────────────────────────────────────────────────────────────────────

export type CollectionTag = {
  id: string;
  name: string;
  aliases: string[];
  description?: string;
};

export const COLLECTION_TAGS: CollectionTag[] = [
  {
    id: 'bts',
    name: 'BTS',
    aliases: ['bangtan', 'bangtan sonyeondan', '방탄소년단', 'bts army'],
    description: 'BTS K-pop group merchandise and collectibles',
  },
  {
    id: 'taylor_swift',
    name: 'Taylor Swift',
    aliases: ['swiftie', 'eras tour', 'ts', 'taylor'],
    description: 'Taylor Swift merchandise across all categories',
  },
  {
    id: 'blackpink',
    name: 'BLACKPINK',
    aliases: ['blink', 'bp'],
    description: 'BLACKPINK K-pop group merchandise',
  },
  {
    id: 'stray_kids',
    name: 'Stray Kids',
    aliases: ['skz', 'stay'],
    description: 'Stray Kids K-pop group merchandise',
  },
  {
    id: 'seventeen',
    name: 'SEVENTEEN',
    aliases: ['svt', 'carat'],
    description: 'SEVENTEEN K-pop group merchandise',
  },
  {
    id: 'disney',
    name: 'Disney',
    aliases: ['mickey', 'minnie', 'disney parks'],
    description: 'Disney collectibles across categories',
  },
  {
    id: 'star_wars',
    name: 'Star Wars',
    aliases: ['sw', 'mandalorian', 'grogu'],
    description: 'Star Wars franchise collectibles',
  },
  {
    id: 'marvel',
    name: 'Marvel',
    aliases: ['mcu', 'avengers', 'spider-man'],
    description: 'Marvel franchise collectibles',
  },
  {
    id: 'dc',
    name: 'DC Comics',
    aliases: ['batman', 'superman', 'justice league'],
    description: 'DC franchise collectibles',
  },
  {
    id: 'anime',
    name: 'Anime',
    aliases: ['dragon ball', 'naruto', 'one piece', 'demon slayer', 'jjk'],
    description: 'Anime franchise collectibles',
  },
  {
    id: 'ghibli',
    name: 'Studio Ghibli',
    aliases: ['totoro', 'spirited away', 'miyazaki', 'howls moving castle'],
    description: 'Studio Ghibli collectibles',
  },
  {
    id: 'hololive',
    name: 'Hololive',
    aliases: ['hololive en', 'myth', 'promise', 'advent'],
    description: 'Hololive VTuber merchandise',
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// Registry API
// ─────────────────────────────────────────────────────────────────────────────

export const ALL_CATEGORIES: CategoryDefinition[] = [
  ...PHASE1_CATEGORIES,
  ...PHASE2_CATEGORIES,
  ...PHASE3_CATEGORIES,
];

export function getCategoryById(categoryId: string): CategoryDefinition | undefined {
  return ALL_CATEGORIES.find((c) => c.id === categoryId);
}

export function getSubtypeById(subtypeId: string): SubtypeDefinition | undefined {
  for (const cat of ALL_CATEGORIES) {
    const subtype = cat.subtypes.find((s) => s.id === subtypeId);
    if (subtype) return subtype;
  }
  return undefined;
}

export function getCategoriesByWave(wave: CategoryWave): CategoryDefinition[] {
  return ALL_CATEGORIES.filter((c) => c.wave === wave);
}

export function getCollectionTagById(tagId: string): CollectionTag | undefined {
  return COLLECTION_TAGS.find((t) => t.id === tagId);
}

export function getAllSubtypes(): SubtypeDefinition[] {
  return ALL_CATEGORIES.flatMap((c) => c.subtypes);
}

/**
 * Get the parent category for a given subtype.
 */
export function getCategoryForSubtype(subtypeId: string): CategoryDefinition | undefined {
  return ALL_CATEGORIES.find((c) => c.subtypes.some((s) => s.id === subtypeId));
}
