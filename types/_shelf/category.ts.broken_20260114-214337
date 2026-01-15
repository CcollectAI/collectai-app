cat > types/category.ts <<'TS'
import { z } from 'zod';

export const CategoryList = [
  'pokemon','mtg','yugioh',
  'funko','designer_toys',
  'lego',
  'diecast',
  'sportscards',
  'retro_handhelds',
  'keycaps','loungefly',
] as const;

export type Category = typeof CategoryList[number];

export const AttrSchemas: Record<Category, z.ZodObject<any>> = {
  // --- TCGs ---
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

  // --- Toys / Figures ---
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

  // --- Bricks ---
  lego: z.object({
    set_number: z.string().optional(),
    theme: z.string().optional(),
    year: z.string().optional(),
    sealed: z.boolean().optional(),
  }),

  // --- Vehicles ---
  diecast: z.object({
    brand: z.string().optional(),           // Hot Wheels, Matchbox, etc.
    series: z.string().optional(),
    scale: z.string().optional(),           // 1:64, 1:18...
    year: z.string().optional(),
    card_condition: z.string().optional(),
    chase: z.boolean().optional(),
  }),

  // --- Sports ---
  sportscards: z.object({
    player: z.string().optional(),
    set: z.string().optional(),
    year: z.string().optional(),
    grade: z.string().optional(),
    variant: z.string().optional(),         // refractor, numbered, auto
  }),

  // --- Tech / Retro ---
  retro_handhelds: z.object({
    console_type: z.string().optional(),    // Game Boy, DS, PSP, Tamagotchi
    model: z.string().optional(),
    colorway: z.string().optional(),
    year: z.string().optional(),
    boxed: z.boolean().optional(),
    working_condition: z.string().optional(),
  }),

  // --- Niches ---
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
};

// Optional: friendly labels for UI
export const CategoryLabels: Record<Category, string> = {
  pokemon: 'Pokémon TCG',
  mtg: 'Magic: The Gathering',
  yugioh: 'Yu-Gi-Oh!',
  funko: 'Funko',
  designer_toys: 'Designer Toys / Art Figures',
  lego: 'LEGO',
  diecast: 'Diecast',
  sportscards: 'Sports Cards',
  retro_handhelds: 'Retro Handhelds',
  keycaps: 'Artisan Keycaps',
  loungefly: 'Loungefly',
};
TS
