import { z } from 'zod';

export const CategoryList = [
  // --- TCGs (6) ---
  'pokemon','mtg','yugioh','lorcana','digimon','one_piece_tcg',

  // --- Toys / Figures (7) ---
  'funko','designer_toys','anime_figures','hot_toys','action_figures','vintage_toys','marvel_legends',

  // --- Building / Models (4) ---
  'lego','gunpla','scale_models','warhammer',

  // --- Gaming (1) ---
  'retro_games',

  // --- Media (6) ---
  'manga','comic_books','bluray_steelbook','anime_bluray','anime_soundtrack','anime_ost_vinyl',

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

  // --- Collectibles (2) ---
  'blind_box','plush_collectibles',

  // --- Lifestyle (3) ---
  'vinyl_records','sneakers','watches',

  // --- Spirits / Luxury (3) ---
  'whiskey','vintage_cameras','pens',

  // --- Legacy (3) ---
  'diecast','sportscards','retro_handhelds',

  // --- New Categories (3) ---
  'oop_board_games','city_pop_vinyl','fragrances',
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
  digimon: z.object({
    set: z.string().optional(),
    number: z.string().optional(),
    color: z.string().optional(),           // red/blue/yellow/green/black/purple/white
    rarity: z.string().optional(),          // common/uncommon/rare/super_rare/secret_rare/alt_art
    language: z.string().optional(),
    grade: z.string().optional(),
  }),
  one_piece_tcg: z.object({
    set: z.string().optional(),             // OP01, OP02, etc.
    number: z.string().optional(),
    color: z.string().optional(),
    rarity: z.string().optional(),          // C/UC/R/SR/SEC/L/SP/manga_art
    variant: z.string().optional(),         // standard/parallel/manga_art
    language: z.string().optional(),
    grade: z.string().optional(),
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
  action_figures: z.object({
    line: z.string().optional(),            // GI Joe, Power Rangers, Transformers, etc.
    scale: z.string().optional(),           // 3.75", 6", 12"
    wave: z.string().optional(),
    packaging_type: z.string().optional(),  // Box Art, Standard, Window Box, Archive
    retailer_exclusive: z.string().optional(),
    sealed: z.boolean().optional(),
  }),
  vintage_toys: z.object({
    era: z.string().optional(),             // 1970s, 1980s, 1990s
    manufacturer: z.string().optional(),    // Kenner, Hasbro, Mattel, TOMY
    item_type: z.string().optional(),       // figure, vehicle, playset, empty_box, proof_card, accessory
    completeness: z.string().optional(),    // CIB, loose_complete, loose_incomplete, box_only
    origin_country: z.string().optional(),
    afa_grade: z.string().optional(),       // AFA 85, AFA 90, etc.
  }),
  marvel_legends: z.object({
    wave: z.string().optional(),
    baf_figure: z.string().optional(),      // Build-A-Figure name
    series: z.string().optional(),          // Standard, Retro, 20th Anniversary, Haslab, Deluxe, Fan Channel
    packaging_type: z.string().optional(),
    retailer_exclusive: z.string().optional(),
    sealed: z.boolean().optional(),
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
    item_category: z.string().optional(),   // miniature, book, codex, rulebook, art_book
    game_system: z.string().optional(),     // 40k, aos, horus_heresy, kill_team
    faction: z.string().optional(),
    kit_name: z.string().optional(),
    kit_type: z.string().optional(),        // HQ, troops, elite, vehicle, centerpiece, titan
    isbn: z.string().optional(),            // ISBN for books/codexes
    author: z.string().optional(),          // Book author (e.g. Dan Abnett)
    publisher: z.string().optional(),       // Black Library, Games Workshop, Forge World
    book_type: z.string().optional(),       // novel, omnibus, codex, battletome, rulebook, art_book
    condition: z.string().optional(),       // new_sealed, new_on_sprue, built, painted, pro_painted
    edition: z.string().optional(),         // standard, limited, special, collector, numbered, oop
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
  comic_books: z.object({
    publisher: z.string().optional(),       // Marvel, DC, Image, Dark Horse, IDW, Boom
    series: z.string().optional(),          // Spider-Man, Batman, Saga, etc.
    issue: z.string().optional(),           // #1, #300, Annual #1
    variant: z.string().optional(),         // 1:25, 1:50, virgin, foil, sketch
    grade: z.string().optional(),           // CGC 9.8, CBCS 9.6, raw NM
    key_issue: z.string().optional(),       // first appearance, death of, origin
    format: z.string().optional(),          // single, TPB, omnibus, hardcover, absolute
    isbn: z.string().optional(),            // ISBN for collected editions
    year: z.string().optional(),
    signed: z.boolean().optional(),
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
  // Lifestyle
  // =========================================================================
  vinyl_records: z.object({
    artist: z.string().optional(),
    album: z.string().optional(),
    label: z.string().optional(),           // Vinyl Me Please, Mondo, Warp, etc.
    pressing: z.string().optional(),        // 1st pressing, repress, limited, numbered
    color: z.string().optional(),           // black, colored, splatter, picture disc
    format: z.string().optional(),          // LP, 2xLP, 7", 10", box set
    rpm: z.string().optional(),             // 33, 45, 78
    genre: z.string().optional(),           // rock, hip-hop, jazz, electronic, soul
    year: z.string().optional(),
    condition: z.string().optional(),       // M, NM, VG+, VG, G+, G, F, P (Goldmine)
    sealed: z.boolean().optional(),
  }),
  sneakers: z.object({
    brand: z.string().optional(),           // Nike, Jordan, Adidas, New Balance, Asics
    model: z.string().optional(),           // Air Jordan 1, Dunk Low, Yeezy 350, etc.
    colorway: z.string().optional(),        // Chicago, Bred, Panda, etc.
    size: z.string().optional(),            // US size
    condition: z.string().optional(),       // DS (deadstock), VNDS, used
    collaboration: z.string().optional(),   // Travis Scott, Off-White, Fragment, etc.
    year: z.string().optional(),
    retail_price: z.string().optional(),
    sku: z.string().optional(),             // style code e.g. DQ8583-100
  }),
  watches: z.object({
    brand: z.string().optional(),           // Rolex, Omega, Seiko, Tudor, Casio, etc.
    model: z.string().optional(),           // Submariner, Speedmaster, SKX007, etc.
    reference: z.string().optional(),       // ref number e.g. 126610LN
    movement: z.string().optional(),        // automatic, manual, quartz, solar
    case_size: z.string().optional(),       // 36mm, 40mm, 42mm
    material: z.string().optional(),        // steel, gold, titanium, ceramic
    year: z.string().optional(),
    box_papers: z.boolean().optional(),     // includes box and papers
    condition: z.string().optional(),       // BNIB, excellent, good, fair, serviced
  }),

  // =========================================================================
  // Collectibles
  // =========================================================================
  blind_box: z.object({
    brand: z.string().optional(),           // Pop Mart, Medicom, Tokidoki, 52Toys
    series: z.string().optional(),          // Labubu, Molly, Dimoo, SkullPanda
    character: z.string().optional(),
    variant: z.string().optional(),         // regular, secret, chase, mega_secret
    sealed: z.boolean().optional(),
    condition: z.string().optional(),
  }),
  plush_collectibles: z.object({
    brand: z.string().optional(),           // Squishmallow, Jellycat, Sanrio, Build-A-Bear
    character: z.string().optional(),
    size: z.string().optional(),            // inches (e.g., 5", 8", 12", 16", 24")
    collection: z.string().optional(),      // Halloween, Valentine's, Easter, Bashful
    exclusive_retailer: z.string().optional(), // Target, Costco, Five Below, Claire's
    has_tags: z.boolean().optional(),
    condition: z.string().optional(),
  }),

  // =========================================================================
  // Spirits / Luxury
  // =========================================================================
  whiskey: z.object({
    brand: z.string().optional(),           // Macallan, Pappy Van Winkle, Yamazaki, etc.
    expression: z.string().optional(),      // Small Batch, Single Barrel, Sherry Cask, etc.
    age_statement: z.string().optional(),   // 12, 15, 18, 25, NAS
    type: z.string().optional(),            // bourbon, scotch, japanese, rye, irish
    proof: z.string().optional(),           // 80, 90, 100, barrel_proof
    bottle_size: z.string().optional(),     // 750ml, 1L, etc.
    vintage_year: z.string().optional(),
    sealed: z.boolean().optional(),
    condition: z.string().optional(),
  }),
  vintage_cameras: z.object({
    brand: z.string().optional(),           // Leica, Nikon, Canon, Hasselblad, Pentax, Mamiya
    model: z.string().optional(),           // M6, FM2, AE-1, 500C/M, K1000, etc.
    camera_type: z.string().optional(),     // SLR, rangefinder, TLR, medium_format, point_and_shoot
    film_format: z.string().optional(),     // 35mm, 120, large_format
    lens_included: z.string().optional(),   // description of lens if included
    serial_number: z.string().optional(),
    working_status: z.string().optional(),  // working, for_parts, CLA_done
    condition: z.string().optional(),
  }),
  pens: z.object({
    brand: z.string().optional(),           // Montblanc, Pelikan, Sailor, Pilot, Visconti, Parker
    model: z.string().optional(),           // 149, Souveran M800, Pro Gear, Custom 823
    pen_type: z.string().optional(),        // fountain, rollerball, ballpoint
    nib_size: z.string().optional(),        // EF, F, M, B, BB, stub
    nib_material: z.string().optional(),    // steel, 14K, 18K, 21K
    filling_system: z.string().optional(),  // piston, cartridge_converter, vacuum, lever
    limited_edition: z.boolean().optional(),
    condition: z.string().optional(),       // mint, near_mint, excellent, good, fair
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

  // =========================================================================
  // New Categories
  // =========================================================================
  oop_board_games: z.object({
    publisher: z.string().optional(),       // Fantasy Flight, CMON, Stonemaier, etc.
    designer: z.string().optional(),        // Uwe Rosenberg, Reiner Knizia, etc.
    player_count: z.string().optional(),    // 1-4, 2-5, etc.
    play_time: z.string().optional(),       // 60min, 90-120min, etc.
    edition: z.string().optional(),         // 1st Edition, Kickstarter Deluxe, Retail, etc.
    bgg_rating: z.string().optional(),      // BoardGameGeek rating
    condition: z.string().optional(),       // sealed, punched_complete, incomplete, damaged_box
    year: z.string().optional(),
  }),
  city_pop_vinyl: z.object({
    artist: z.string().optional(),          // Tatsuro Yamashita, Mariya Takeuchi, etc.
    album: z.string().optional(),
    label: z.string().optional(),           // Nippon Columbia, Air Records, etc.
    pressing: z.string().optional(),        // OG pressing, reissue, remaster
    color: z.string().optional(),           // black, colored, picture disc
    format: z.string().optional(),          // LP, 2xLP, 7", 12"
    year: z.string().optional(),
    condition: z.string().optional(),       // M, NM, VG+, VG, G+, G (Goldmine)
    obi: z.boolean().optional(),            // Japanese OBI strip included
  }),
  fragrances: z.object({
    house: z.string().optional(),           // MFK, Tom Ford, Creed, Xerjoff, Versace, YSL, etc.
    fragrance_name: z.string().optional(),
    concentration: z.string().optional(),   // EDT, EDP, Extrait, Parfum
    size_ml: z.string().optional(),         // 30, 50, 100, 200
    gender: z.string().optional(),          // unisex, masculine, feminine
    fragrance_family: z.string().optional(), // woody, oriental, floral, fresh, oud
    fill_level: z.string().optional(),      // full, 90%, 75%, 50%, partial
    batch_code: z.string().optional(),
    year: z.string().optional(),
  }),
};

// Friendly labels for UI
export const CategoryLabels: Record<Category, string> = {
  // TCGs
  pokemon: 'Pokemon TCG',
  mtg: 'Magic: The Gathering',
  yugioh: 'Yu-Gi-Oh!',
  lorcana: 'Disney Lorcana',
  digimon: 'Digimon TCG',
  one_piece_tcg: 'One Piece TCG',

  // Toys / Figures
  funko: 'Funko Pop',
  designer_toys: 'Designer Toys',
  anime_figures: 'Anime Figures & Statues',
  hot_toys: 'Hot Toys & Movie Statues',
  action_figures: 'Action Figures',
  vintage_toys: 'Vintage Toys',
  marvel_legends: 'Marvel Legends',

  // Building / Models
  lego: 'LEGO',
  gunpla: 'Gunpla (Gundam Kits)',
  scale_models: 'Scale Model Kits',
  warhammer: 'Warhammer & Tabletop',

  // Gaming
  retro_games: 'Retro Video Games',

  // Media
  manga: 'Manga',
  comic_books: 'Comic Books & Graphic Novels',
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

  // Collectibles
  blind_box: 'Blind Box & Mystery Figures',
  plush_collectibles: 'Plush Collectibles',

  // Lifestyle
  vinyl_records: 'Vinyl Records',
  sneakers: 'Sneakers & Kicks',
  watches: 'Watches',

  // Spirits / Luxury
  whiskey: 'Whiskey & Spirits',
  vintage_cameras: 'Vintage Cameras',
  pens: 'Fountain Pens & Writing',

  // Legacy
  diecast: 'Diecast',
  sportscards: 'Sports Cards',
  retro_handhelds: 'Retro Handhelds',

  // New Categories
  oop_board_games: 'OOP Board Games & KS Exclusives',
  city_pop_vinyl: 'City Pop & Future Funk Vinyl',
  fragrances: 'Fragrances',
};
