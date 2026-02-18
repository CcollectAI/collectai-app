import { z } from 'zod';

export const CategoryList = [
  // --- TCGs (4) ---
  'pokemon','mtg','yugioh','lorcana',

  // --- Toys / Figures (4) ---
  'funko','designer_toys','anime_figures','hot_toys',

  // --- Building / Models (4) ---
  'lego','gunpla','scale_models','warhammer',

  // --- Gaming (1) ---
  'retro_games',

  // --- Media (5) ---
  'manga','bluray_steelbook','anime_bluray','anime_soundtrack','anime_ost_vinyl',

  // --- Music / Fandom (4) ---
  'kpop_merch','taylor_swift','pop_fandom','kpop_lightsticks',

  // --- Disney / Theme Parks (3) ---
  'disney','theme_park','ghibli',

  // --- Japan Exclusives (3) ---
  'bandai_premium','jp_magazine','jp_event',

  // --- Nintendo / Pokemon Merch (2) ---
  'nintendo_merch','retro_pokemon',

  // --- IP-Specific (2) ---
  'one_piece','vtuber',

  // --- Niche (2) ---
  'keycaps','loungefly',

  // --- Legacy (3) ---
  'diecast','sportscards','retro_handhelds',
] as const;

export type Category = typeof CategoryList[number];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const AttrSchemas: Record<Category, z.ZodObject<any>> = {
  // =========================================================================
  // TCGs
  // =========================================================================
  pokemon: z.object({
    set: z.string().optional(),
    number: z.string().optional(),          // e.g., 4/102
    language: z.string().optional(),
    printing: z.string().optional(),        // 1st, shadowless, etc.
    rarity: z.string().optional(),
    grade: z.string().optional(),
  }),
  mtg: z.object({
    set: z.string().optional(),
    collector_no: z.string().optional(),
    language: z.string().optional(),
    edition: z.string().optional(),         // alpha/beta/unlimited/etc.
    foil: z.boolean().optional(),
    grade: z.string().optional(),
  }),
  yugioh: z.object({
    set: z.string().optional(),
    number: z.string().optional(),
    language: z.string().optional(),
    rarity: z.string().optional(),
    edition: z.string().optional(),         // 1st ed/unlimited
    grade: z.string().optional(),
  }),
  lorcana: z.object({
    set: z.string().optional(),
    number: z.string().optional(),
    color: z.string().optional(),           // amber/amethyst/emerald/ruby/sapphire/steel
    rarity: z.string().optional(),          // common/uncommon/rare/super_rare/legendary
    variant: z.string().optional(),         // standard/foil/enchanted
    language: z.string().optional(),
  }),

  // =========================================================================
  // Toys / Figures
  // =========================================================================
  funko: z.object({
    line: z.string().optional(),            // Pop, Soda, etc.
    number: z.string().optional(),
    exclusive: z.string().optional(),       // retailer exclusive
    sticker_variant: z.string().optional(),
    box_condition: z.string().optional(),
  }),
  designer_toys: z.object({
    brand: z.string().optional(),           // Bearbrick, KAWS, Pop Mart, etc.
    series: z.string().optional(),
    figure_name: z.string().optional(),
    size: z.string().optional(),            // 100%, 400%, 1000%, etc.
    edition: z.string().optional(),         // retail, collab, limited, chase
    release_year: z.string().optional(),
  }),
  anime_figures: z.object({
    manufacturer: z.string().optional(),    // Good Smile, Kotobukiya, Alter, Bandai
    series: z.string().optional(),          // anime/game franchise
    character: z.string().optional(),
    scale: z.string().optional(),           // 1/4, 1/7, 1/8, non-scale
    type: z.string().optional(),            // scale_figure, nendoroid, figma, prize, garage_kit
    condition: z.string().optional(),       // new_sealed, opened, damaged_box
    release_year: z.string().optional(),
  }),
  hot_toys: z.object({
    franchise: z.string().optional(),       // Marvel, Star Wars, DC, etc.
    character: z.string().optional(),
    scale: z.string().optional(),           // 1/6, 1/4, life-size
    edition: z.string().optional(),         // standard, deluxe, special, exclusive
    mms_number: z.string().optional(),      // Hot Toys MMS catalog number
    condition: z.string().optional(),
    release_year: z.string().optional(),
  }),

  // =========================================================================
  // Building / Models
  // =========================================================================
  lego: z.object({
    set_number: z.string().optional(),
    theme: z.string().optional(),
    year: z.string().optional(),
    sealed: z.boolean().optional(),
  }),
  gunpla: z.object({
    grade: z.string().optional(),           // HG, RG, MG, PG, SD
    series: z.string().optional(),          // UC, Wing, SEED, IBO, etc.
    mobile_suit: z.string().optional(),
    scale: z.string().optional(),           // 1/144, 1/100, 1/60
    version: z.string().optional(),         // Ver.Ka, Ver.2.0, P-Bandai
    built: z.boolean().optional(),
  }),
  scale_models: z.object({
    brand: z.string().optional(),           // Tamiya, Hasegawa, Revell, Airfix
    subject: z.string().optional(),         // aircraft, tank, ship, car
    scale: z.string().optional(),           // 1/72, 1/48, 1/35, 1/350
    era: z.string().optional(),             // WWII, modern, sci-fi
    built: z.boolean().optional(),
    condition: z.string().optional(),
  }),
  warhammer: z.object({
    game_system: z.string().optional(),     // 40k, aos, horus_heresy, kill_team
    faction: z.string().optional(),
    kit_name: z.string().optional(),
    kit_type: z.string().optional(),        // HQ, troops, elite, vehicle, centerpiece, titan
    condition: z.string().optional(),       // new_on_sprue, built, painted, pro_painted
    points: z.string().optional(),
  }),

  // =========================================================================
  // Gaming
  // =========================================================================
  retro_games: z.object({
    platform: z.string().optional(),        // NES, SNES, N64, GB, GBA, Genesis, PS1, etc.
    title: z.string().optional(),
    region: z.string().optional(),          // NTSC, PAL, JP
    completeness: z.string().optional(),    // loose, CIB, sealed, graded
    condition: z.string().optional(),
    year: z.string().optional(),
  }),

  // =========================================================================
  // Media
  // =========================================================================
  manga: z.object({
    title: z.string().optional(),
    publisher: z.string().optional(),       // VIZ, Kodansha, Dark Horse, Tokyopop
    volume: z.string().optional(),          // single vol number or "complete set"
    language: z.string().optional(),
    printing: z.string().optional(),        // 1st, later, OOP
    condition: z.string().optional(),
  }),
  bluray_steelbook: z.object({
    title: z.string().optional(),
    studio: z.string().optional(),          // Criterion, Arrow, Shout Factory, etc.
    format: z.string().optional(),          // 4K UHD, Blu-ray, DVD
    edition: z.string().optional(),         // steelbook, slipcover, mediabook, limited
    region: z.string().optional(),          // A, B, C, free
    sealed: z.boolean().optional(),
  }),
  anime_bluray: z.object({
    title: z.string().optional(),
    studio: z.string().optional(),          // Aniplex, Funimation, Sentai, JP release
    format: z.string().optional(),          // BD box set, BD single, LD
    region: z.string().optional(),
    limited: z.boolean().optional(),        // limited/numbered run
    extras: z.string().optional(),          // booklet, art box, soundtrack CD
    sealed: z.boolean().optional(),
  }),
  anime_soundtrack: z.object({
    title: z.string().optional(),
    anime: z.string().optional(),           // associated anime/game
    format: z.string().optional(),          // CD, vinyl, cassette
    label: z.string().optional(),
    catalog_no: z.string().optional(),
    edition: z.string().optional(),         // standard, limited, event, preorder bonus
    sealed: z.boolean().optional(),
  }),
  anime_ost_vinyl: z.object({
    title: z.string().optional(),
    anime: z.string().optional(),
    label: z.string().optional(),           // Tiger Lab, Milan, King Records, etc.
    color: z.string().optional(),           // vinyl color variant
    pressing: z.string().optional(),        // 1st pressing, repress, etc.
    rpm: z.string().optional(),             // 33, 45
    sealed: z.boolean().optional(),
  }),

  // =========================================================================
  // Music / Fandom
  // =========================================================================
  kpop_merch: z.object({
    artist: z.string().optional(),          // BTS, Blackpink, Stray Kids, etc.
    item_type: z.string().optional(),       // photocard, album, lightstick, poster, fansign
    album: z.string().optional(),
    version: z.string().optional(),         // specific album version
    member: z.string().optional(),          // specific member for photocards
    official: z.boolean().optional(),       // official vs. fanmade
  }),
  taylor_swift: z.object({
    item_type: z.string().optional(),       // vinyl, CD, merch, ticket, signed
    album: z.string().optional(),
    variant: z.string().optional(),         // color variant, store exclusive
    era: z.string().optional(),             // tour era (Eras, 1989, etc.)
    signed: z.boolean().optional(),
    sealed: z.boolean().optional(),
  }),
  pop_fandom: z.object({
    artist: z.string().optional(),          // Ariana Grande, Olivia Rodrigo, etc.
    item_type: z.string().optional(),       // vinyl, merch, poster, tour item
    variant: z.string().optional(),
    tour: z.string().optional(),
    signed: z.boolean().optional(),
    condition: z.string().optional(),
  }),
  kpop_lightsticks: z.object({
    artist: z.string().optional(),
    version: z.string().optional(),         // v1, v2, v3, special edition
    tour_exclusive: z.boolean().optional(),
    bluetooth: z.boolean().optional(),
    condition: z.string().optional(),
    year: z.string().optional(),
  }),

  // =========================================================================
  // Disney / Theme Parks
  // =========================================================================
  disney: z.object({
    item_type: z.string().optional(),       // pin, figure, plush, art, ears, ornament
    franchise: z.string().optional(),       // classic Disney, Pixar, Marvel, Star Wars
    collection: z.string().optional(),
    park_exclusive: z.boolean().optional(),
    limited_edition: z.boolean().optional(),
    year: z.string().optional(),
  }),
  theme_park: z.object({
    park: z.string().optional(),            // Disneyland, WDW, Tokyo Disney, USJ, etc.
    item_type: z.string().optional(),       // pin, popcorn bucket, figure, apparel, prop
    event: z.string().optional(),           // anniversary, seasonal, grand opening
    year: z.string().optional(),
    region: z.string().optional(),          // US, JP, EU, HK
    limited_edition: z.boolean().optional(),
  }),
  ghibli: z.object({
    film: z.string().optional(),            // Spirited Away, Totoro, Mononoke, etc.
    item_type: z.string().optional(),       // figure, plush, art, cel, music box
    manufacturer: z.string().optional(),    // Donguri Sora, Benelic, etc.
    jp_exclusive: z.boolean().optional(),
    vintage: z.boolean().optional(),
    condition: z.string().optional(),
  }),

  // =========================================================================
  // Japan Exclusives
  // =========================================================================
  bandai_premium: z.object({
    line: z.string().optional(),            // S.H.Figuarts, Robot Spirits, Chogokin
    franchise: z.string().optional(),
    item_name: z.string().optional(),
    p_bandai: z.boolean().optional(),       // P-Bandai web exclusive
    tamashii_exclusive: z.boolean().optional(),
    release_year: z.string().optional(),
  }),
  jp_magazine: z.object({
    magazine: z.string().optional(),        // Dengeki, Newtype, Animedia, Famitsu
    issue: z.string().optional(),
    insert_type: z.string().optional(),     // poster, figure, code, artbook, clear file
    franchise: z.string().optional(),
    year: z.string().optional(),
    condition: z.string().optional(),
  }),
  jp_event: z.object({
    event: z.string().optional(),           // Comiket, Wonder Festival, AnimeJapan
    season: z.string().optional(),          // Summer/Winter + year
    item_type: z.string().optional(),       // figure, doujin, tapestry, acrylic stand
    circle: z.string().optional(),          // doujin circle / manufacturer
    franchise: z.string().optional(),
    limited_quantity: z.boolean().optional(),
  }),

  // =========================================================================
  // Nintendo / Pokemon Merch
  // =========================================================================
  nintendo_merch: z.object({
    franchise: z.string().optional(),       // Pokemon, Mario, Zelda, Kirby, Splatoon
    item_type: z.string().optional(),       // plush, figure, amiibo, apparel, art
    store_exclusive: z.string().optional(), // Pokemon Center, Nintendo Store, etc.
    region: z.string().optional(),          // JP, US, EU
    year: z.string().optional(),
    sealed: z.boolean().optional(),
  }),
  retro_pokemon: z.object({
    item_type: z.string().optional(),       // Pokedex toy, Game Boy accessory, plush, card binder
    generation: z.string().optional(),      // Gen 1, Gen 2, etc.
    brand: z.string().optional(),           // TOMY, Hasbro, Tiger Electronics, etc.
    year: z.string().optional(),
    working: z.boolean().optional(),
    boxed: z.boolean().optional(),
  }),

  // =========================================================================
  // IP-Specific
  // =========================================================================
  one_piece: z.object({
    item_type: z.string().optional(),       // figure, card, plush, art, ichiban kuji
    character: z.string().optional(),
    manufacturer: z.string().optional(),    // Megahouse, Bandai, Banpresto
    line: z.string().optional(),            // Portrait of Pirates, Figuarts ZERO, etc.
    scale: z.string().optional(),
    condition: z.string().optional(),
  }),
  vtuber: z.object({
    vtuber: z.string().optional(),          // Hololive, Nijisanji, indie
    character: z.string().optional(),
    item_type: z.string().optional(),       // acrylic stand, tapestry, badge, voice pack
    event: z.string().optional(),           // birthday, anniversary, concert
    official: z.boolean().optional(),
    year: z.string().optional(),
  }),

  // =========================================================================
  // Niche
  // =========================================================================
  keycaps: z.object({
    maker: z.string().optional(),
    sculpt: z.string().optional(),
    colorway: z.string().optional(),
    profile: z.string().optional(),         // Cherry/SA/DSA/KAT/...
    material: z.string().optional(),        // resin/metal
    run_size: z.string().optional(),
    drop_date: z.string().optional(),
  }),
  loungefly: z.object({
    license: z.string().optional(),         // Disney, Marvel, etc.
    collection: z.string().optional(),
    retailer: z.string().optional(),        // BoxLunch, Hot Topic, etc.
    era: z.enum(['pre-funko','funko']).optional(),
    drop_date: z.string().optional(),
    condition: z.string().optional(),
  }),

  // =========================================================================
  // Legacy (kept from original app)
  // =========================================================================
  diecast: z.object({
    brand: z.string().optional(),           // Hot Wheels, Matchbox, etc.
    series: z.string().optional(),
    scale: z.string().optional(),           // 1:64, 1:18...
    year: z.string().optional(),
    card_condition: z.string().optional(),
    chase: z.boolean().optional(),
  }),
  sportscards: z.object({
    player: z.string().optional(),
    set: z.string().optional(),
    year: z.string().optional(),
    grade: z.string().optional(),
    variant: z.string().optional(),         // refractor, numbered, auto
  }),
  retro_handhelds: z.object({
    console_type: z.string().optional(),    // Game Boy, DS, PSP, Tamagotchi
    model: z.string().optional(),
    colorway: z.string().optional(),
    year: z.string().optional(),
    boxed: z.boolean().optional(),
    working_condition: z.string().optional(),
  }),
};

// Friendly labels for UI
export const CategoryLabels: Record<Category, string> = {
  // TCGs
  pokemon: 'Pokemon TCG',
  mtg: 'Magic: The Gathering',
  yugioh: 'Yu-Gi-Oh!',
  lorcana: 'Disney Lorcana',

  // Toys / Figures
  funko: 'Funko Pop',
  designer_toys: 'Designer Toys',
  anime_figures: 'Anime Figures & Statues',
  hot_toys: 'Hot Toys & Movie Statues',

  // Building / Models
  lego: 'LEGO',
  gunpla: 'Gunpla (Gundam Kits)',
  scale_models: 'Scale Model Kits',
  warhammer: 'Warhammer & Tabletop',

  // Gaming
  retro_games: 'Retro Video Games',

  // Media
  manga: 'Manga',
  bluray_steelbook: 'Blu-ray & Steelbooks',
  anime_bluray: 'Anime Blu-ray Box Sets',
  anime_soundtrack: 'Anime Soundtracks',
  anime_ost_vinyl: 'Anime OST Vinyl & CD',

  // Music / Fandom
  kpop_merch: 'K-pop Merch',
  taylor_swift: 'Taylor Swift',
  pop_fandom: 'Pop Fandom Merch',
  kpop_lightsticks: 'K-pop Lightsticks',

  // Disney / Theme Parks
  disney: 'Disney Collectibles',
  theme_park: 'Theme Park Exclusives',
  ghibli: 'Studio Ghibli',

  // Japan Exclusives
  bandai_premium: 'Bandai Premium',
  jp_magazine: 'JP Magazine Exclusives',
  jp_event: 'JP Event Exclusives',

  // Nintendo / Pokemon Merch
  nintendo_merch: 'Nintendo & Pokemon Merch',
  retro_pokemon: 'Retro Pokemon Accessories',

  // IP-Specific
  one_piece: 'One Piece',
  vtuber: 'VTuber Merch',

  // Niche
  keycaps: 'Artisan Keycaps',
  loungefly: 'Loungefly',

  // Legacy
  diecast: 'Diecast',
  sportscards: 'Sports Cards',
  retro_handhelds: 'Retro Handhelds',
};
