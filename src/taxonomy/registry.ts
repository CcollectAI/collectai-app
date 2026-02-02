/**
 * Versioned Taxonomy Registry
 *
 * Defines category waves (rollout phases) and collection tags.
 * Categories drive schemas/pricing/prefill. Collection tags drive UX grouping.
 *
 * Design:
 * - category_id: canonical category (e.g., 'warhammer_minis')
 * - subtype_id: finer granularity (e.g., 'warhammer_books' vs 'warhammer_minis')
 * - collections: orthogonal tags (e.g., ['taylor_swift', 'eras_tour'])
 */

export const TAXONOMY_VERSION = '2026.02.02';

// ─────────────────────────────────────────────────────────────────────────────
// Category Wave Phases
// ─────────────────────────────────────────────────────────────────────────────

export type CategoryWave = 'phase1' | 'phase2' | 'phase3' | 'special';

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
// Phase 1 Categories (Core TCG + Toys)
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
    subtypes: [
      { id: 'yugioh_cards', name: 'Cards', keywords: ['card', 'starlight', 'ghost', 'ultimate', 'secret'] },
      { id: 'yugioh_sealed', name: 'Sealed Product', keywords: ['booster', 'box', 'sealed', 'pack', 'tin'] },
      { id: 'yugioh_graded', name: 'Graded Cards', keywords: ['psa', 'bgs', 'cgc', 'graded', 'slab'] },
    ],
  },
  {
    id: 'funko',
    name: 'Funko Pop!',
    wave: 'phase1',
    subtypes: [
      { id: 'funko_pop', name: 'Pop! Vinyl', keywords: ['pop', 'vinyl', 'funko'] },
      { id: 'funko_chase', name: 'Chase Variants', keywords: ['chase', 'variant', 'exclusive', 'limited'] },
      { id: 'funko_sdcc', name: 'Convention Exclusives', keywords: ['sdcc', 'nycc', 'eccc', 'wondercon', 'convention'] },
    ],
  },
  {
    id: 'lorcana',
    name: 'Disney Lorcana',
    wave: 'phase1',
    subtypes: [
      { id: 'lorcana_cards', name: 'Cards', keywords: ['card', 'enchanted', 'legendary'] },
      { id: 'lorcana_sealed', name: 'Sealed Product', keywords: ['booster', 'box', 'starter', 'sealed'] },
    ],
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// Phase 2 Categories (Hobby + Collectibles)
// ─────────────────────────────────────────────────────────────────────────────

const PHASE2_CATEGORIES: CategoryDefinition[] = [
  {
    id: 'warhammer',
    name: 'Warhammer',
    wave: 'phase2',
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
    id: 'gunpla',
    name: 'Gunpla / Model Kits',
    wave: 'phase2',
    subtypes: [
      { id: 'gunpla_hg', name: 'High Grade (HG)', keywords: ['hg', 'high grade', '1/144'] },
      { id: 'gunpla_mg', name: 'Master Grade (MG)', keywords: ['mg', 'master grade', '1/100'] },
      { id: 'gunpla_pg', name: 'Perfect Grade (PG)', keywords: ['pg', 'perfect grade', '1/60'] },
      { id: 'gunpla_rg', name: 'Real Grade (RG)', keywords: ['rg', 'real grade'] },
      { id: 'gunpla_other', name: 'Other Kits', keywords: ['sd', 'entry', 'fm', 'full mechanics'] },
    ],
  },
  {
    id: 'designer_toys',
    name: 'Designer Toys',
    wave: 'phase2',
    subtypes: [
      { id: 'designer_kaws', name: 'KAWS', keywords: ['kaws', 'companion', 'medicom'] },
      { id: 'designer_bearbrick', name: 'Be@rbrick', keywords: ['bearbrick', 'be@rbrick', '100%', '400%', '1000%'] },
      { id: 'designer_other', name: 'Other Designer', keywords: ['superplastic', 'coarse', 'good smile'] },
    ],
  },
  {
    id: 'lego',
    name: 'LEGO',
    wave: 'phase2',
    subtypes: [
      { id: 'lego_sealed', name: 'Sealed Sets', keywords: ['sealed', 'nib', 'misb', 'new'] },
      { id: 'lego_retired', name: 'Retired Sets', keywords: ['retired', 'discontinued', 'rare'] },
      { id: 'lego_minifigs', name: 'Minifigures', keywords: ['minifig', 'cmf', 'collectible minifigure'] },
    ],
  },
  {
    id: 'diecast',
    name: 'Diecast & Hot Wheels',
    wave: 'phase2',
    subtypes: [
      { id: 'diecast_hotwheels', name: 'Hot Wheels', keywords: ['hot wheels', 'hotwheels', 'mainline', 'th', 'sth'] },
      { id: 'diecast_matchbox', name: 'Matchbox', keywords: ['matchbox'] },
      { id: 'diecast_premium', name: 'Premium Diecast', keywords: ['autoart', 'minichamps', 'spark', '1:18', '1:43'] },
    ],
  },
  {
    id: 'sportscards',
    name: 'Sports Cards',
    wave: 'phase2',
    subtypes: [
      { id: 'sportscards_basketball', name: 'Basketball', keywords: ['basketball', 'nba', 'prizm', 'select', 'optic'] },
      { id: 'sportscards_football', name: 'Football', keywords: ['football', 'nfl', 'prizm', 'select', 'optic'] },
      { id: 'sportscards_baseball', name: 'Baseball', keywords: ['baseball', 'mlb', 'topps', 'bowman'] },
      { id: 'sportscards_soccer', name: 'Soccer', keywords: ['soccer', 'football', 'topps', 'panini', 'prizm'] },
    ],
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// Phase 3 Categories (Niche + Emerging)
// ─────────────────────────────────────────────────────────────────────────────

const PHASE3_CATEGORIES: CategoryDefinition[] = [
  {
    id: 'keycaps',
    name: 'Artisan Keycaps',
    wave: 'phase3',
    subtypes: [
      { id: 'keycaps_artisan', name: 'Artisan', keywords: ['artisan', 'sculpt', 'resin'] },
      { id: 'keycaps_gmk', name: 'GMK Sets', keywords: ['gmk', 'keyset', 'doubleshot'] },
    ],
  },
  {
    id: 'retro_handhelds',
    name: 'Retro Handhelds',
    wave: 'phase3',
    subtypes: [
      { id: 'retro_gameboy', name: 'Game Boy', keywords: ['gameboy', 'game boy', 'gba', 'gbc', 'gbp'] },
      { id: 'retro_psp', name: 'PSP / Vita', keywords: ['psp', 'vita', 'playstation portable'] },
      { id: 'retro_other', name: 'Other Handhelds', keywords: ['lynx', 'game gear', 'neo geo pocket'] },
    ],
  },
  {
    id: 'loungefly',
    name: 'Loungefly',
    wave: 'phase3',
    subtypes: [
      { id: 'loungefly_bags', name: 'Mini Backpacks', keywords: ['backpack', 'mini', 'bag'] },
      { id: 'loungefly_wallets', name: 'Wallets', keywords: ['wallet', 'cardholder'] },
    ],
  },
  {
    id: 'vinyl_records',
    name: 'Vinyl Records',
    wave: 'phase3',
    subtypes: [
      { id: 'vinyl_lp', name: 'LPs', keywords: ['lp', 'vinyl', 'album', '12"', '12 inch'] },
      { id: 'vinyl_limited', name: 'Limited Pressings', keywords: ['limited', 'numbered', 'colored', 'splatter'] },
    ],
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// Special Categories (Artist Collections / Memorabilia)
// ─────────────────────────────────────────────────────────────────────────────

const SPECIAL_CATEGORIES: CategoryDefinition[] = [
  {
    id: 'music_memorabilia',
    name: 'Music Memorabilia',
    wave: 'special',
    description: 'Includes artist-specific items (BTS, Taylor Swift, etc.)',
    subtypes: [
      { id: 'music_albums', name: 'Albums & CDs', keywords: ['album', 'cd', 'vinyl', 'record'] },
      { id: 'music_photocards', name: 'Photocards', keywords: ['photocard', 'pc', 'photo card', 'pob'] },
      { id: 'music_lightsticks', name: 'Lightsticks', keywords: ['lightstick', 'light stick', 'army bomb'] },
      { id: 'music_posters', name: 'Posters & Prints', keywords: ['poster', 'print', 'signed'] },
      { id: 'music_merch', name: 'Official Merchandise', keywords: ['merch', 'official', 'tour'] },
    ],
  },
  {
    id: 'apparel',
    name: 'Collectible Apparel',
    wave: 'special',
    description: 'Fashion items from artists, brands, collabs',
    subtypes: [
      { id: 'apparel_tops', name: 'Tops & Hoodies', keywords: ['hoodie', 'shirt', 'tee', 'sweater', 'jacket'] },
      { id: 'apparel_bottoms', name: 'Bottoms', keywords: ['pants', 'shorts', 'jeans'] },
      { id: 'apparel_accessories', name: 'Accessories', keywords: ['hat', 'cap', 'bag', 'belt', 'scarf'] },
    ],
  },
  {
    id: 'instruments',
    name: 'Musical Instruments',
    wave: 'special',
    description: 'Guitars, signed instruments, etc.',
    subtypes: [
      { id: 'instruments_guitars', name: 'Guitars', keywords: ['guitar', 'fender', 'gibson', 'acoustic', 'electric'] },
      { id: 'instruments_signed', name: 'Signed Instruments', keywords: ['signed', 'autograph', 'autographed'] },
      { id: 'instruments_other', name: 'Other Instruments', keywords: ['ukulele', 'piano', 'keyboard', 'drum'] },
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
    description: 'Taylor Swift merchandise across all categories (music, apparel, instruments)',
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
];

// ─────────────────────────────────────────────────────────────────────────────
// Registry API
// ─────────────────────────────────────────────────────────────────────────────

export const ALL_CATEGORIES: CategoryDefinition[] = [
  ...PHASE1_CATEGORIES,
  ...PHASE2_CATEGORIES,
  ...PHASE3_CATEGORIES,
  ...SPECIAL_CATEGORIES,
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
