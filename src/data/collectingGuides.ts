/**
 * Beginner guides, per category.
 *
 * Content source: "Collectors App: Category & Value Master Guide" (2026-08-14).
 * Seven categories, chosen because they are the most active in the app.
 *
 * WHY A TYPED MODULE RATHER THAN A TABLE
 * --------------------------------------
 * Seven guides need no CMS, and a module cannot be half-written at runtime: a
 * DB-backed guide with three of six sections filled renders a page that looks
 * broken, and nothing fails loudly. Keying on `CategoryId` also makes the
 * "does this slug exist?" check a COMPILE error rather than a script — a guide
 * for a category that was renamed stops the build instead of rendering a CTA
 * that opens nothing.
 *
 * WHY `Partial`
 * -------------
 * Most categories have no guide, and that is the normal case, not a gap. The
 * category screen must render its call-to-action ONLY where `guideFor()`
 * returns something — a banner on all 56 categories would dead-end on 49 of
 * them, which is the empty-shelf failure this codebase keeps paying for.
 *
 * ENGLISH ONLY, DELIBERATELY (v1)
 * -------------------------------
 * This is content, not UI chrome, so it is NOT routed through i18n. The parity
 * gate requires every key in all 6 locales, and putting ~70 prose strings
 * through it would mean shipping nothing until they are translated six times.
 * The chrome around the guide (titles, buttons) does use i18n keys.
 */

import type { CategoryId } from './categories';

export type GuideTerm = {
  term: string;
  definition: string;
};

export type GuidePick = {
  /** The item itself, as a collector would name it. */
  title: string;
  /** Why it sits at this end of the market. */
  why: string;
};

export type CollectingGuide = {
  /** One or two sentences on what this hobby actually is. */
  intro: string;
  /** The words a newcomer will hit in listings and not understand. */
  glossary: GuideTerm[];
  /** How not to destroy the thing you just bought. */
  care: string;
  /** The specific way beginners lose money here. */
  watchOut: { title: string; body: string };
  /** What actually moves price in this category. */
  valueDrivers: string;
  /** The famous unobtainable one — aspiration, and a sense of the ceiling. */
  holyGrail: GuidePick;
  /** Where a beginner can actually start, with real money. */
  entryLevel: GuidePick;
};

export const COLLECTING_GUIDES: Partial<Record<CategoryId, CollectingGuide>> = {
  pokemon: {
    intro:
      'Pokémon collecting runs on nostalgia, artwork and the thrill of chasing rare cards. It is very easy to start, and the high end is fiercely competitive.',
    glossary: [
      { term: 'Chase card', definition: 'The rarest, most sought-after card in a set — a Secret Rare Charizard, an Alternate Art Umbreon.' },
      { term: 'Holo / Reverse holo', definition: '"Holo" means the artwork is shiny. "Reverse holo" means everything except the artwork is foil-treated.' },
      { term: 'Grading (PSA/BGS/CGC)', definition: 'Sending a card to a third party who authenticates it and grades its condition from 1 to 10.' },
    ],
    care:
      'Put high-value pulls straight into a soft penny sleeve, then a rigid toploader. If you use a binder, choose a side-loading, ringless one — rings dent cards near the spine.',
    watchOut: {
      title: 'Counterfeits are everywhere',
      body: 'Look for missing surface texture, incorrect or thin fonts, washed-out back colours, and paper that feels unusually light.',
    },
    valueDrivers:
      'Grading scores dominate — a PSA 10 can be worth 10–50x the same card ungraded. Then character premiums (Charizard, Pikachu, Umbreon) and vintage scarcity against modern pull rates.',
    holyGrail: {
      title: '1998 Pikachu Illustrator / 1st Edition Base Set Charizard (PSA 10)',
      why: 'The Illustrator was never sold in packs — it went to about 40 winners of a 1998 Japanese contest. The 1st Edition Charizard is the peak of vintage nostalgia in flawless condition.',
    },
    entryLevel: {
      title: 'Modern bulk and non-holo rares',
      why: 'Billions of cards are printed every year. Commons, uncommons and non-competitive rares flood the market while everyone chases the top hits, so they cost pennies.',
    },
  },

  mtg: {
    intro:
      'Magic: The Gathering is the original trading card game, from 1993. Cards are collected for artwork and lore, but value is tied tightly to actual play.',
    glossary: [
      { term: 'The Reserved List', definition: 'A closed list of early cards Wizards of the Coast promised never to reprint, which guarantees permanent scarcity.' },
      { term: 'Foil / Etched', definition: 'Reflective finish treatments. Etched foils have a textured, subtler metallic sheen.' },
      { term: 'Formats (Commander, Standard)', definition: 'Rulesets. Demand in Commander, the most popular casual format, drives a lot of prices.' },
    ],
    care:
      'Double-sleeve anything valuable: a tight inner sleeve inserted bottom-up, then a standard outer sleeve top-down. That protects against spills and dust from both directions.',
    watchOut: {
      title: 'Reprints and power creep',
      body: 'Any card not on the Reserved List can be reprinted, which expands supply and can deflate a secondary price overnight.',
    },
    valueDrivers:
      'Permanent scarcity (Reserved List status), competitive and Commander utility, and artificial micro-scarcity such as serialised cards numbered to 500.',
    holyGrail: {
      title: 'Alpha Black Lotus / the serialised 1-of-1 "The One Ring"',
      why: 'Black Lotus is the iconic, game-breaking card from Magic\'s 1993 genesis. The 1-of-1 "The One Ring" was a unique Elvish-script card bought by Post Malone for over $2 million.',
    },
    entryLevel: {
      title: 'Draft chaff and Standard staples',
      why: 'Booster packs produce a lot of cards useful only in limited play. Unplayable or recently reprinted cards sell for $0.10 to $1.00.',
    },
  },

  yugioh: {
    intro:
      'Yu-Gi-Oh! is known for fast gameplay, iconic anime ties and intricate foil rarities. The secondary market is volatile and driven by competition and nostalgia.',
    glossary: [
      { term: '1st Edition', definition: 'Cards from a set\'s initial print run, marked with a stamp. Strongly preferred over later "Unlimited" runs.' },
      { term: 'Special rarities', definition: 'Ultra-rare holographic treatments — Starlight Rare, Ghost Rare, Quarter Century Secret Rare.' },
      { term: 'Errata', definition: 'An official change to a card\'s text or rules effect, which alters how it plays in tournaments.' },
    ],
    care:
      'Yu-Gi-Oh! cards are Japanese size, smaller than Magic or Pokémon. Always buy Small/Japanese-size sleeves — standard sleeves let the card slide around and damage its corners.',
    watchOut: {
      title: 'Banlist swings',
      body: 'Konami updates competitive banlists periodically. A $100 tournament staple that gets forbidden can lose most of its value instantly.',
    },
    valueDrivers:
      '1st Edition vintage status, extreme pull-rate foil rarities, and character nostalgia from the original anime run.',
    holyGrail: {
      title: '1999 Tournament Stainless Steel Black Luster Soldier',
      why: 'A literal 1-of-1, printed on metal and awarded to the winner of the first national tournament in Tokyo.',
    },
    entryLevel: {
      title: 'Structure deck reprints and Mega-Tins',
      why: 'Konami reprints tournament staples aggressively in pre-made $12 structure decks and annual tins to keep the game accessible.',
    },
  },

  // The guide's K-pop section is specifically about PHOTOCARDS. The app has no
  // photocard slug, so it lives on the nearest real category rather than
  // inventing one — adding a category to host a guide would put a 57th entry
  // through five registration points and every category checker.
  kpop_merch: {
    intro:
      'Photocards are credit-card-sized collectible photos included in albums or handed out at promotional events. The market is vibrant and community-driven.',
    glossary: [
      { term: 'POB (pre-order benefit)', definition: 'Exclusive photocards given only to people who pre-order an album through a specific retailer.' },
      { term: 'Lomo cards', definition: 'Fan-made, unofficial replicas. Fine for decoration, but no resale or trade value at all.' },
      { term: 'WTT / WTB / WTS', definition: 'Community shorthand: want to trade, want to buy, want to sell.' },
    ],
    care:
      'Use acid-free, PVC-free sleeves — this one is not optional. PVC releases acidic gases over time that react with the ink and permanently ruin a card.',
    watchOut: {
      title: 'Trading scams',
      body: 'When trading online, always ask for video proof: a clip showing the card under light, next to a piece of paper with the seller\'s handle and the date.',
    },
    valueDrivers:
      'Member popularity imbalances, event exclusivity where you had to attend in person, and limited pop-up store distribution.',
    holyGrail: {
      title: 'BTS "Butterful Night" broadcast cards / rookie-era fan-sign photocards',
      why: 'Broadcast cards went only to fans who physically attended exclusive live tapings in Korea, often limited to 100–300 attendees.',
    },
    entryLevel: {
      title: 'Standard album pulls',
      why: 'Top groups sell millions of physical albums, so ordinary album cards are widely available for $3 to $8.',
    },
  },

  warhammer: {
    intro:
      'Warhammer is a tabletop strategy game combining model assembly, painting and competitive play. It attracts dedicated hobbyists and painters worldwide.',
    glossary: [
      { term: 'Sprue', definition: 'The plastic frame that holds unassembled miniature parts as they come from the factory.' },
      { term: 'Kitbashing', definition: 'Customising models by combining parts from different kits to build something unique.' },
      { term: 'NOS / NIB', definition: '"New on sprue" and "new in box".' },
    ],
    care:
      'Paint chips easily. Transport figures on magnetised bases inside metal-lined cases, and seal finished models with a protective matte varnish.',
    watchOut: {
      title: 'The "pile of shame"',
      body: 'Beginners buy several large army boxes at once. Assembly and painting take tens of hours — finish one squad before buying the next.',
    },
    valueDrivers:
      'Discontinued out-of-print metals and resins, army box exclusivity, and high-level professional painting to "Golden Demon" commission standard.',
    holyGrail: {
      title: 'Forge World Warlord Titan / Golden Demon trophy winners',
      why: 'The Warlord Titan is a 22-inch resin model costing $2,000+ unassembled. Award-winning custom-painted pieces function as one-of-a-kind art.',
    },
    entryLevel: {
      title: 'Unpainted second-hand infantry',
      why: 'Overwhelmed collectors regularly offload basic grey plastic on the secondary market at steep discounts.',
    },
  },

  dnd: {
    intro:
      'Dungeons & Dragons collecting centres on tabletop accessories: rare rulebook printings, metal and artisan dice sets, and campaign miniatures.',
    glossary: [
      { term: 'Polyhedral set', definition: 'The core seven dice required for play — d4, d6, d8, d10, d00, d12 and d20.' },
      { term: 'Chonk', definition: 'An oversized centrepiece d20, made for display or a dramatic roll.' },
      { term: 'TTRPG', definition: 'Tabletop role-playing game.' },
    ],
    care:
      'Never roll sharp-edged resin, gemstone or glass dice on an unpadded hard surface — use a felt or leather tray. Store vintage hardcover rulebooks upright to preserve the binding.',
    watchOut: {
      title: 'Unbalanced factory dice',
      body: 'Cheap mass-produced plastic dice often contain interior air pockets that bias rolls toward particular numbers.',
    },
    valueDrivers:
      'Publication age (the 1970s TSR original era), book condition — unmarked pages and pristine spines — and artisan hand-crafted materials like dichroic glass or semi-precious stone.',
    holyGrail: {
      title: '1974 "White Box" original D&D set (woodgrain print)',
      why: 'Hand-assembled in Gary Gygax\'s basement and limited to roughly 1,000 initial copies. It is the foundational artifact of modern roleplaying.',
    },
    entryLevel: {
      title: 'Standard acrylic dice and current 5E rulebooks',
      why: 'Injection-moulded dice and current-generation hardcovers are produced in enormous volume and are available everywhere.',
    },
  },

  anime_figures: {
    intro:
      'Anime collecting focuses on statues, articulated action figures and display models. The community cares about character accuracy, official licensing and pristine boxes.',
    glossary: [
      { term: 'Scale figure', definition: 'A high-end statue built to a precise proportion of the character\'s canonical height, such as 1/7 or 1/4.' },
      { term: 'Prize figure', definition: 'A more accessible figure made primarily as a reward for Japanese arcade claw machines.' },
      { term: 'Nendoroid / Figma', definition: 'Popular Good Smile Company lines — chibi designs, or posable joints with interchangeable parts.' },
    ],
    care:
      'Direct sunlight and heat warp PVC and bleach paint pigments. Keep figures in a climate-controlled spot away from windows, and dust regularly with a soft makeup brush.',
    watchOut: {
      title: 'Bootleg statues',
      body: 'Counterfeits are rampant on discount retail sites. Tells include a glossy or sticky PVC finish, misaligned eye decals, bad joints and missing holographic licensing stickers.',
    },
    valueDrivers:
      'Scale size, manufacturer prestige (Alter, Good Smile, Prime 1), low production run limits, and unpainted resin "garage kits".',
    holyGrail: {
      title: 'Prime 1 Studio 1/3 scale resin statues / 1:1 life-size figures',
      why: 'Polystone masterpieces weighing over 50 lbs with intricate lighting and micro-detail, retailing from $1,500 to $10,000+.',
    },
    entryLevel: {
      title: 'Prize figures (Banpresto, Sega, Pop Up Parade)',
      why: 'Mass-produced PVC figures made for low-cost prize distribution, widely available between $20 and $40.',
    },
  },
};

/** The guide for a category, or null when none exists — which is the normal
 *  case for most of the 56 categories. Callers MUST branch on null rather than
 *  rendering a call-to-action that opens nothing. */
export function guideFor(categoryId: string | null | undefined): CollectingGuide | null {
  if (!categoryId) return null;
  return COLLECTING_GUIDES[categoryId as CategoryId] ?? null;
}

/** Category slugs that have a guide. Used to decide where the beginner
 *  "start here" surface can send someone. */
export const GUIDED_CATEGORY_IDS = Object.keys(COLLECTING_GUIDES) as CategoryId[];
