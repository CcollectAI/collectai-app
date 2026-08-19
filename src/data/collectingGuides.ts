/**
 * Beginner guides, per category.
 *
 * Content source: "Collectors App: Category & Value Master Guide" (2026-08-14),
 * plus Lorcana (2026-08-15), whose numbers were checked against live price
 * guides rather than taken from the master doc, which predates the set, and
 * Digimon + One Piece TCG, K-pop lightsticks, Taylor Swift and pens
 * (2026-08-16), whose numbers were all read off mv_catalog_item_price
 * directly.
 * ALL 55 categories now have one (completed 2026-08-16).
 * NOTE: anime_figures (statues/scales) and action_figures (NECA/Mezco/SHF) are
 * SEPARATE categories in the app and have separate guides; so do kpop_merch
 * (photocards) and kpop_lightsticks.
 *
 * WHY A TYPED MODULE RATHER THAN A TABLE
 * --------------------------------------
 * Fifty-five guides need no CMS, and a module cannot be half-written at runtime: a
 * DB-backed guide with three of six sections filled renders a page that looks
 * broken, and nothing fails loudly. Keying on `CategoryId` also makes the
 * "does this slug exist?" check a COMPILE error rather than a script — a guide
 * for a category that was renamed stops the build instead of rendering a CTA
 * that opens nothing.
 *
 * WHY `Partial` — AND WHY THE NULL BRANCH STILL MATTERS
 * -----------------------------------------------------
 * This used to say "most categories have no guide, and that is the normal
 * case". As of 2026-08-16 that is no longer true: all 55 have one, so
 * `guideFor()` does not return null for any current category.
 *
 * The type stays `Partial` and every caller MUST keep branching on null, for
 * two reasons that outlive today's coverage: a new category added to
 * `CATEGORIES` starts life without a guide, and a renamed slug silently
 * un-guides an existing one. The branch is now insurance rather than the
 * common path — deleting it would make the next added category render a
 * call-to-action that opens nothing, which is the empty-shelf failure this
 * codebase keeps paying for.
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
  /**
   * What the category IS and what its culture assumes you already know.
   *
   * Still typed optional so a new guide can be added without it, but as of
   * 2026-08-16 ALL 24 guides carry one. The earlier rule — "deliberately
   * absent from the obvious ones, nobody needs to be told what a watch is" —
   * was wrong about what this paragraph is for. It is not a dictionary
   * definition; it is the context that makes the rest of the page make sense:
   *   - watches: reference numbers, originality, why patina is a virtue
   *   - pens: nib grinders, pen shows, modern LE vs vintage restoration
   *   - Taylor Swift: easter eggs, eras, the number 13, why "Taylor's Version"
   *     is a separate object rather than a replacement
   *   - comics: ages, keys, and why grading split reading from owning
   * A reader who does not know that Charizard outsells mechanically identical
   * cards, or that a set "retires", cannot use the value section at all.
   *
   * The rest of a guide assumes you already know roughly what you are looking
   * at. This is the paragraph that earns that assumption.
   */
  whatItIs?: string;
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
    whatItIs:
      'Pokémon cards have been printed since 1996, and the hobby splits into two crowds who barely overlap. Players buy singles for tournaments and care what a card does. Collectors care about the artwork, the set symbol and the grade, and often never take a card out of its sleeve. Nearly all the money sits on the collector side, which is why a card that is useless in play can cost a hundred times one that wins games.\n\nCards arrive in sets of a few hundred, three or four times a year, each stamped with a small set symbol that identifies it forever. Rarity is marked in the bottom corner — circle for common, diamond for uncommon, star for rare — and above that sits a shifting cast of special treatments: full art, alternate art, secret rare, gold. Those treatments are where the value concentrates, and their names change every few years while the idea stays the same: a small number of cards per set are printed far less often than the rest.\n\nThree eras matter to a beginner. Wizards of the Coast printed the game from 1999 to 2003, and those cards (Base Set, Jungle, Fossil) are the vintage tier — small print runs, handled by children, so survivors in good condition are genuinely scarce. The middle era, roughly 2003 to 2010, introduced Gold Stars and the EX cards. Everything after is modern, printed in enormous quantities to meet demand, where scarcity is manufactured by pull rate rather than by time. The most expensive card in our Pokémon catalogue is a 2000s Gold Star Umbreon at €7,524.\n\nThe single most important cultural fact is Charizard. A Charizard card outsells a card of nearly any other creature and has done for twenty-five years. In our catalogue the 1999 Base Set holo Charizard is €1,469 while Blastoise, the same set at the same rarity, is €175 and most of the other fifteen Base Set holos are under €100. Grading is the other thing to understand early: sending a card to PSA, BGS or CGC gets it authenticated, graded 1–10 and sealed in a slab, and the difference between a 9 and a 10 on a valuable card is routinely a multiple, not a percentage.',
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
    whatItIs:
      'Magic: The Gathering was invented by Richard Garfield in 1993 and every trading card game since has copied its shape. Two players are duelling wizards, each casting spells from a deck they built themselves out of a pool that now runs past 25,000 different cards. It is the oldest game in this app by a decade, and that history is exactly why it collects well: cards printed in the 1990s were made in small quantities for a game nobody knew would last, and they were played with rather than stored.\n\nThe market has two halves that barely meet. Players buy singles they intend to shuffle, and their prices move with tournament results and with Commander, the hugely popular casual format that drives more demand than competitive play does. Collectors buy sealed product and graded cards they will never open. A card can be expensive because it wins games, because it is beautiful, or because it is old and scarce — and those three reasons rarely apply to the same card.\n\nThe one piece of Magic-specific law worth knowing on day one is the Reserved List: a closed list of early cards Wizards of the Coast promised in the 1990s never to reprint. That promise is why Alpha and Beta staples hold value in a way no other game\'s cards do — supply is fixed permanently by policy rather than by how many survived. Everything not on that list can and does get reprinted, which expands supply and can deflate a price overnight, so "will this be reprinted?" is the first question about any expensive modern card.\n\nVocabulary moves fast, but three terms carry most listings. Foil and etched describe reflective finishes. Formats — Standard, Modern, Commander, Legacy — describe which cards are legal where, and a card banned in one format can crater or spike depending on demand elsewhere. Serialised cards, numbered to a stated quantity, are Wizards\' modern attempt at manufactured scarcity, and they behave quite differently from the genuinely old scarcity of the Reserved List.',
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
    whatItIs:
      'Yu-Gi-Oh! began as a game inside a 1996 manga and was released as a real card game by Konami in 1999. It is the largest catalogue in this app — nearly 59,000 distinct cards — and it plays and collects unlike anything else here, so a beginner coming from Pokémon or Magic should expect their instincts to be wrong.\n\nThe game itself is famously fast: turns can involve long chains of effects, and the competitive metagame turns over quickly as Konami releases new sets and revises the Forbidden and Limited list, which bans or restricts cards outright. That list is the central price mechanism on the player side. A card put to one per deck loses most of its demand overnight; a card released from the list can multiply in a week. No other game in this app has a single document that moves prices that sharply.\n\nRarity is where Yu-Gi-Oh! is genuinely different. Instead of one chase treatment per set, it has a deep ladder — Common, Rare, Super, Ultra, Secret, Ultimate, Ghost, Starlight and more — and the SAME card is printed at several of them across different sets. So "Blue-Eyes White Dragon" is not one object with one price; it is dozens of printings spanning twenty-five years, from a €1 common to a four-figure first-edition Secret. Reading the set code stamped on the card, not the card name, is the skill that separates a beginner from someone who knows what they are buying.\n\nThe vintage tier is the 2002–2004 English releases and the earlier Japanese ones, where print runs were small and the audience was children. Note one structural fact about this category in the app: 58,835 catalogue rows but almost no live buyable listings, because Yu-Gi-Oh! singles trade mostly through specialist card shops rather than the marketplaces we read. The catalogue depth is real; the supply figure is a reflection of where this game is bought.',
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

  lorcana: {
    intro:
      'Disney Lorcana is a trading card game built entirely from Disney characters. It launched in August 2023, which makes it the youngest market in the app — and the only one where you can still watch a collectible market form from the beginning.',
    whatItIs:
      'Disney Lorcana is a trading card game made by Ravensburger under licence from Disney, launched in August 2023. It is the youngest market in this app by two decades, which makes it the one place you can watch a collectible market form from the beginning rather than inherit one already shaped.\n\nYou play an Illumineer, summoning Disney characters as "glimmers" and racing your opponent to gather twenty points of lore. Every card belongs to one of six inks — Amber, Amethyst, Emerald, Ruby, Sapphire and Steel — and a deck may use only two, which makes deckbuilding a constraint rather than a shopping list. Cards you can play face-down as a resource are marked inkable; the stronger uninkable cards cost you that flexibility. None of this affects collecting directly, but it explains why certain cards are in demand at all.\n\nFor collecting the structure is simple and worth learning immediately. The chase rarity is Enchanted: a full-art, fully-foiled version of an existing card, seeded very thinly into boosters. Enchanted cards carry nearly all the value in every set. Below them, ordinary rares and commons are printed to demand and cost very little, because Ravensburger prints to meet a modern audience rather than to a 1990s guess.\n\nThe one thing that makes Lorcana different from every other game here is that nothing is old enough to be scarce by attrition. A card is only rare until Ravensburger prints more of it, and they have shown they will. The First Chapter behaves differently — smallest print run of any main set, never reprinted — which is why its Enchanted Elsa, Spirit of Winter sits at €824 while the Enchanted Elsa from set 11 is €354. Chasing a spiking card from a set still in production is the classic way a beginner loses money here.',
    glossary: [
      { term: 'Enchanted', definition: 'The chase rarity — a full-art, fully-foiled version of an existing card, seeded very thinly into booster packs. This is what carries the value in almost every set.' },
      { term: 'Inkable', definition: 'A card with an inkwell symbol beside its cost, meaning it can be played face-down as a resource instead of being cast. Uninkable cards are stronger but stiffer to play.' },
      { term: 'Lore', definition: 'The score. Characters you send questing earn lore, and the first player to twenty wins.' },
    ],
    care:
      'Treat it exactly like any other card game: penny sleeves for anything you play with, a toploader for anything you would be upset to bend. Lorcana foils curl in humidity more readily than most, so keep them flat and out of a hot room rather than standing them in a warm window.',
    watchOut: {
      title: 'Reprints, not age, set the price here',
      body: 'Nothing in Lorcana is old enough to be scarce by attrition, so a card is only rare until Ravensburger prints more of it — and they have shown they will. Chasing a spiking card from a set still in production is how beginners lose money in this category. The First Chapter behaves differently precisely because it has never been reprinted.',
    },
    valueDrivers:
      'Enchanted rarity above everything else, then whether the set has ever been reprinted, then the character — Elsa, Mickey and Stitch cards consistently outsell equally rare cards of less popular characters. Grading matters more here than in older games, because a three-year-old card in anything less than pristine condition has no excuse.',
    holyGrail: {
      title: 'Elsa – Spirit of Winter (Enchanted, The First Chapter #207)',
      why: 'The most valuable card in the game by a wide margin — around $644 near-mint raw, with PSA 10 copies crossing $1,500. The First Chapter had the smallest print run of any main set and has never been reprinted, so it is the one place in Lorcana where scarcity is real rather than temporary.',
    },
    entryLevel: {
      title: 'Singles from the current set, or a starter deck',
      why: 'Current-set commons and uncommons are printed to demand and cost very little, and a starter deck gets you a playable pair of inks for roughly the price of two booster packs. Both are a far better first purchase than a sealed box.',
    },
  },

  // digimon and one_piece_tcg added 2026-08-16. Chosen on catalogue data, not
  // vibes: they are the 5th and 6th largest catalogues in the app (9,135 and
  // 6,990 priced rows) and carry MORE live buyable listings than Lorcana
  // (22,816 and 22,500 in 30 days). Every number below was read off
  // mv_catalog_item_price rather than taken from a market article.
  digimon: {
    intro:
      'The Digimon Card Game is Bandai’s card game built on the Digimon franchise, relaunched in 2020 and still printing hard. It is one of the deepest catalogues in the app, and one of the cheapest to start: half of every card we track sells for under a euro.',
    whatItIs:
      'The Digimon Card Game is Bandai\'s card game, relaunched in 2020 and printing steadily since. It shares only its creatures with the 1999 virtual pets and the anime — as a game and as a market it is entirely modern, and it is the fifth-largest catalogue in this app with more live buyable listings than any of the three big TCGs.\n\nThe game is built around digivolving: you stack a bigger Digimon on top of a smaller one already in play, so a turn is about building a chain rather than casting one large card. Your resource is a memory gauge shared with your opponent, which is why a turn that feels free hands them the next one. Cards carry a colour, a level and a play cost. For collecting purposes, none of that matters as much as one fact: Bandai prints in waves and reprints willingly, so scarcity here is a decision rather than an accident.\n\nThe value ladder is short and easy to learn. Alternate-art cards — commonly labelled "Rare Pull" or parallel — sit at the top, with textured foil versions of popular Digimon above the plain ones. ACE cards, playable early at a memory cost, are chased in every recent set. X Antibody variants (Omnimon X, Magnamon X) are separate cards that consistently outprice their normal counterparts. The plain version of a card whose Rare Pull foil costs €1,760 — WarGreymon, top of our Digimon catalogue — is frequently under a euro.\n\nThe trap specific to this category is sealed product. Look at the top of the market and much of it is Booster Box Cases, not cards — Dual Revolution at €1,335, Digital World Shambala at €1,250. That is speculation on sealed stock in a game whose publisher reprints aggressively, and it is the easiest way to lose money here. Half of every card we track sells for under a euro, so the singles market is genuinely cheap; the boxes are where beginners overcommit.',
    glossary: [
      { term: 'Rare Pull / parallel', definition: 'An alternate-art version of a card seeded thinly into packs. These sit at the very top of the market — the two most expensive singles we track are both Rare Pull foils.' },
      { term: 'Textured', definition: 'A card with a raised, patterned foil finish, used for the chase versions of popular Digimon. Commands a large premium over the plain foil of the same card.' },
      { term: 'ACE', definition: 'A card type introduced in later sets that can be played early for less memory, at the cost of handing memory back. Powerful, heavily chased, and printed in every recent set.' },
      { term: 'X Antibody', definition: 'A variant line of Digimon (Omnimon X, Magnamon X) printed as separate cards. The textured X Antibody versions are consistently among the most expensive cards in their sets.' },
    ],
    care:
      'Sleeve anything you play with — Digimon foils are printed on a stock that shows edge wear quickly, and a played-out foil loses most of its premium. Keep textured cards out of stacks under pressure: the raised finish is what you are paying for, and it flattens. Sealed product needs a cool, dry shelf and no direct sun; a sun-faded box is worth a fraction of a clean one.',
    watchOut: {
      title: 'Most of the expensive "cards" here are sealed boxes, not cards',
      body: 'Look at the top of the market and it is full of Booster Box Cases — Dual Revolution at around €1,335, Digital World Shambala at €1,250, Dawn of Liberator at €995. That is not collecting, it is speculating on sealed stock, and it is the single easiest way to lose money in this category: Bandai reprints aggressively, and a case bought at release can be worth less a year later while the singles inside it hold. Buy the card you actually want.',
    },
    valueDrivers:
      'Rarity treatment first — Rare Pull and Textured versions carry almost all the value, and the plain version of the same card is often a euro. Then the Digimon itself: Omnimon, WarGreymon, MetalGarurumon and Alphamon appear again and again at the top regardless of set. Then set: sets that have never had a reprint hold up, and Release Special Boosters (the reprint sets) do not. Condition matters at the top end and barely at all below it — with a median price of €0.99, grading a common costs more than the card.',
    holyGrail: {
      title: 'WarGreymon (Rare Pull) — BT19-20, foil',
      why: 'The most expensive single in our Digimon catalogue at about €1,760, with MetalGarurumon from the same set right behind it at €1,380. The pattern is worth learning from: the ceiling in this game is a Rare Pull of a character everyone already loved in 1999, not a mechanically strong card.',
    },
    entryLevel: {
      title: 'A starter deck, then singles from the set you like',
      why: 'The median card we track costs €0.99 and 95% of them are under €28, so almost the entire game is affordable one card at a time. A starter deck gives you a playable colour for roughly the price of two boosters, and singles let you buy the exact art you want instead of paying for the chance at it.',
    },
  },

  one_piece_tcg: {
    intro:
      'The One Piece Card Game launched in 2022 and became the fastest-growing card game in years. It is the most top-heavy market in the app: the typical card costs about €1.21, and the most expensive one we track is €9,154.',
    whatItIs:
      'The One Piece Card Game is Bandai\'s card game based on the manga, released in Japan in July 2022 and in English that December. It grew faster than any card game in recent memory, and it is the most top-heavy market in this app: the typical card costs about €1.21 and the most expensive one we track is €9,154.\n\nEvery deck is built around a Leader card, which sits face-up from the start and dictates which colours you may play — you pick your captain before anything else. Attacking is powered by DON!! cards, a separate deck of resources you attach to characters to push their power, which is why a board that looks even can swing on how much DON!! is left. Knowing this matters for collecting mainly because Leader cards and the characters people build around hold demand independently of rarity.\n\nThe treatments are where the money is, and there are four worth knowing. Alternate art (parallel) is a different illustration of an existing card, pulled far less often — almost everything expensive in this game is one. Manga rare prints the card as a black-and-white manga panel and is the rarest treatment in the game. SP is a special foil given to a handful of cards per set. Serial-numbered promos, handed out at championships, are the true ceiling: the numbered Portgas D. Ace at €9,154 was never sold at all.\n\nTwo structural facts shape prices. English print runs arrived in waves, and OP01 Romance Dawn\'s first wave was tiny: a sealed Wave 1 (blue) booster box is €5,498 in our catalogue while the Wave 2 (white) reprint of the same box is €1,594. And the game is young enough that Bandai can and does reprint, so a card from a set still in production can fall hard when the next wave lands. High prices plus heavy alternate-art demand also make this the most counterfeited category in the app — fakes now copy foiling and texture convincingly, so expensive singles are bought graded or from sellers who photograph the actual card.',
    glossary: [
      { term: 'Alternate Art / Parallel', definition: 'A different illustration of an existing card, pulled far less often. Almost everything expensive in this game is an alternate art rather than a distinct card.' },
      { term: 'Manga rare', definition: 'A card illustrated as a black-and-white manga panel. The rarest treatment in the game — the Manga Luffy from PRB-01 sits around €5,640.' },
      { term: 'SP', definition: 'A "special" foil treatment given to a handful of cards per set. Boa Hancock (SP) from EB-02 is about €6,410.' },
      { term: 'Serial numbered', definition: 'Tournament and championship promos stamped with an individual number. These are the true ceiling: the numbered Portgas D. Ace is the single most expensive item in this category.' },
    ],
    care:
      'Double-sleeve anything above about €50 and put it in a toploader or a rigid holder — at this category’s price points a corner ding is worth more than most people’s whole collection elsewhere. Alternate arts are usually foil and curl in humidity, so store them flat rather than upright in a warm room. For anything expensive enough to grade, do not clean it, do not trim it, and do not send it in a penny sleeve alone.',
    watchOut: {
      title: 'This is the easiest category in the app to get faked',
      body: 'High prices plus heavy alternate-art demand is exactly the combination counterfeiters want, and One Piece fakes have got good — including foiling and texture. Buy expensive singles graded, or from a seller with real feedback and photos of the actual card, never a stock image. The second trap is print waves: OP01 Romance Dawn is expensive because the early English run was tiny, and cards from sets still in print can fall hard when the next wave lands.',
    },
    valueDrivers:
      'Treatment above everything — serial-numbered promos, Manga rares, SPs and alternate arts hold nearly all the value, and the base version of the same card is often a euro or two. Then the character: Luffy, Ace, Boa Hancock, Yamato and Sabo recur at the top. Then print run — OP01 and championship promos are scarce in a way later sets are not. Condition and grading matter more here than in any other card game in the app, simply because the numbers are big enough to justify the fee.',
    holyGrail: {
      title: 'Portgas D. Ace (Serial Numbered promo)',
      why: 'About €9,154, the most expensive single item in our entire One Piece catalogue — a numbered tournament promo rather than a set card, which is the point: the ceiling here is prizes that were never sold, not pack pulls.',
    },
    entryLevel: {
      title: 'A Starter Deck plus base-rarity singles',
      why: 'Starter decks are complete, playable and cheap, and the median card we track is €1.21. Buying the regular version of a card whose alternate art costs four figures gets you the same card in play for pocket money — the gap between them is art and scarcity, not function.',
    },
  },

  // The guide's K-pop section is specifically about PHOTOCARDS. The app has no
  // photocard slug, so it lives on the nearest real category rather than
  // inventing one — adding a category to host a guide would put a 57th entry
  // through five registration points and every category checker.
  kpop_merch: {
    intro:
      'Photocards are credit-card-sized collectible photos included in albums or handed out at promotional events. The market is vibrant and community-driven.',
    whatItIs:
      "Every album ships in several versions, each version holds a random card, and each card shows one member — so completing a release means chasing one specific face out of a randomised pool, usually by trading for it. That is the part outsiders miss: this market runs on fan communities rather than shops, prices follow which member is popular this year, and a card that was never sold at all — because you had to physically attend a fan-sign in Seoul to receive it — outranks anything you could have bought.",
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
    whatItIs:
      "Warhammer is Games Workshop's tabletop wargame, and it is not sold finished. You buy a box of unassembled plastic or resin parts still attached to the frames they were moulded on, clip them out, glue them together and paint them, then play battles against someone else's army using a rulebook. There are two settings — Warhammer 40,000 in a grim far future, and Age of Sigmar in fantasy. For collecting, the consequence that matters is this: current kits are permanently available at list price and therefore carry no premium whatsoever. The value sits entirely in what Games Workshop has stopped making, and in models somebody has painted to an exceptional standard.",
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
    whatItIs:
      "Dungeons & Dragons is the tabletop roleplaying game that started the entire genre in 1974. There is no board and no pieces to move. A group of players describe what their characters do, one player called the Dungeon Master describes the world and what happens back, and dice settle anything uncertain. Because there is no product you are required to buy in order to play, collecting here is not about cards or figures at all — it is about early printings of the rulebooks, particularly the 1970s TSR era, alongside dice and painted miniatures. The books are the market, and their condition matters far more than newcomers expect.",
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
    whatItIs:
      "Almost all of it is designed and produced in Japan, under licence from the studio that made the show. The category then splits cleanly in two. Scale figures are high-end display pieces built to a precise fraction of the character's canonical height, sold months ahead by pre-order, manufactured once in roughly the quantity ordered and then never made again — which is why a figure can be unobtainable a year after it shipped. Prize figures are the opposite: cheap, mass-produced, and originally distributed as prizes in Japanese arcade machines. Both are worth owning; only one of them appreciates.",
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

  // kpop_lightsticks is SEPARATE from kpop_merch above, which is specifically
  // about photocards. Different object, different failure modes, and both
  // categories exist in the app with their own catalogues.
  kpop_lightsticks: {
    intro:
      'Every K-pop group sells an official lightstick, and fans buy the one belonging to the group they support. They are the most recognisable object in the hobby, and the discontinued ones are quietly among the hardest merchandise to replace.',
    whatItIs:
      'A lightstick is a battery-powered handheld light in a shape unique to one group — BIGBANG’s is a crown, B.A.P’s is a Matoki, Seventeen’s is nicknamed the Carat Bong. You hold it at concerts, where many of them sync by Bluetooth so the whole arena changes colour together, which is the point of owning the official one rather than a generic glow stick. Each group also numbers its versions (Ver. 1, Ver. 2, Ver. 3) and usually stops making the old one, so a lightstick is only on sale for a window. This category also carries the rest of the official-goods shelf — membership kits, season’s greetings, cupsleeve sets and tour merchandise.',
    glossary: [
      { term: 'Official vs. unofficial', definition: 'Official goods come from the group’s own company. Unofficial ("fanmade") copies are everywhere, are usually cheaper and lighter, and are worth close to nothing resale.' },
      { term: 'Ver. 1 / Ver. 2 / Ver. 3', definition: 'Successive redesigns of the same group’s lightstick. Earlier versions are discontinued and priced by scarcity rather than by looks.' },
      { term: 'Membership kit', definition: 'The physical welcome pack for a paid fanclub membership, sold for one season only. IVE’s 2025 kit and TWICE’s ONCE kit sit around €300 and €175 in our catalogue.' },
      { term: 'Cupsleeve set', definition: 'Merchandise made for a fan-run café event, produced in tiny numbers for one occasion. The most expensive item we track in this category is one of these.' },
    ],
    care:
      'Take the batteries out if you are storing it — a leaking cell inside a discontinued lightstick is the one damage you cannot repair. Keep the box: for this category the packaging is part of the item, and a sealed or boxed example is worth substantially more than a loose one. Bright light yellows white plastic over years, so display it out of direct sun.',
    watchOut: {
      title: 'Fanmade copies are sold as official constantly',
      body: 'Unofficial lightsticks copy the shape closely and are common on general marketplaces. Check for the company hologram, the correct box and manual, and a serial where the group uses one. If a current-generation lightstick is being sold well below the group’s own shop price, that is the reason. Buy from a K-pop specialist rather than a general listing when you can.',
    },
    valueDrivers:
      'Whether it is still in production, first. A group that disbanded — I.O.I, 2NE1, 4Minute, GFRIEND, B.A.P — can never issue another one, and those sit at €120–200 while current groups’ sticks stay near retail. Then condition and box. Then the group’s size, though not as much as you would expect: a small disbanded group can outprice a huge current one. Version matters too, and Ver. 1 of a long-running group is usually the scarce one.',
    holyGrail: {
      title: 'TWICE Momo Birthday Cupsleeve Set (2025)',
      why: 'About €962, the most expensive item in our lightstick catalogue — and it is not a lightstick at all. A fan-event set made once, in tiny numbers, for one birthday. That is the shape of the ceiling here: one-occasion goods, not the mass-produced flagship item.',
    },
    entryLevel: {
      title: 'The official lightstick of a group that is still active',
      why: 'Half of what we track sells under €44, and a current group’s official stick is available from their own shop at retail. Buy the one for the group you actually listen to — it is the only purchase in this category that is equally good as an object and as a hold.',
    },
  },

  taylor_swift: {
    intro:
      'Taylor Swift merchandise is one of the largest single-artist collecting markets in the world. It runs on deliberate variants — the same album pressed in a dozen colours, editions and exclusives — and on the enormous premium attached to her signature.',
    whatItIs:
      'Collecting Taylor Swift makes very little sense until you understand that her fanbase is built on decoding. She hides clues — "easter eggs" — in liner notes, video frames, outfit colours and social posts, and fans decode them for months before a release. The number 13 runs through everything: her birthday, her lucky number, the number she used to draw on her hand at shows, and the reason a track 13 or a 13-second detail is never accidental. Each album has its own visual identity, which fans call an "era", and merchandise is bought and sorted by era rather than by year. The re-recordings — the albums labelled "Taylor\'s Version" — came out of a dispute over who owned her original masters; they include previously unreleased "vault" tracks, and to a collector they are separate objects from the originals, not replacements. Knowing all of this is what tells you why a specific coloured vinyl with a particular track order is worth ten times another pressing of the same album.',
    glossary: [
      { term: 'Variant', definition: 'The same album issued in a different colour, cover or packaging, often exclusive to one retailer or country. Variants are the basic unit of this hobby.' },
      { term: 'RSD', definition: 'Record Store Day — an annual event with pressings made only for independent shops, in fixed and usually small quantities.' },
      { term: "TV / Taylor's Version", definition: 'Her re-recordings of the first six albums. They are separate releases and collect separately from the originals rather than replacing them.' },
      { term: 'COA', definition: 'Certificate of authenticity for a signed item. Only as good as the company that issued it — see the warning below.' },
    ],
    care:
      'Store vinyl upright and never flat-stacked, out of heat, in outer sleeves; a warped record is worth a fraction of a flat one. Keep signed items out of daylight entirely — signatures fade, and a faded autograph cannot be restored. Anything signed on paper or card is better framed with UV glass than left in a sleeve where it can be handled.',
    watchOut: {
      title: 'The signature is where the money and the fraud both are',
      body: 'Signed items dominate the top of this market — signed CDs and vinyl from €874 to €1,744 in our catalogue — which makes it the most forged Taylor Swift product by a distance. A certificate of authenticity proves nothing on its own; plenty of worthless ones are printed by the same people selling the fake. Prefer items authenticated by a recognised third party, or bought from the official store when a signed edition is sold there directly.',
    },
    valueDrivers:
      'Signature first, and by a wide margin. Then scarcity of the pressing: Record Store Day and retailer-exclusive colours were made once in fixed numbers, which is why the 1989 Crystal Clear RSD vinyl is the most expensive item we track at about €3,260. Then condition, which for sealed records means the seal, and then era — debut and Fearless material predates the fanbase’s current size, so far less of it survives in good shape.',
    holyGrail: {
      title: '1989 Crystal Clear Vinyl (Record Store Day)',
      why: 'Around €3,260. A one-off RSD pressing of the album that made her a global pop act, in a colour that was never repeated — scarcity fixed at the moment of manufacture, which is the only kind that lasts.',
    },
    entryLevel: {
      title: 'Standard-edition CDs and current-tour merchandise',
      why: 'The median item we track is about €35. Standard pressings and official tour merch are printed in enormous numbers, cost very little, and are the sane place to start — the four-figure end of this market is signed, and signed is where beginners get burned.',
    },
  },

  // No `whatItIs`: a fountain pen needs no introduction, and the type doc calls
  // this out specifically as a category where explaining the object would read
  // as padding.
  pens: {
    intro:
      'Fountain pen collecting is the most expensive category in this app by some distance — the typical pen we track sells for about €300, and the ceiling is over €160,000. It is a small, knowledgeable market built on limited editions and traditional craft.',
    whatItIs:
      'Fountain pens are a small, deeply knowledgeable hobby with its own social world: pen shows, nib grinders who reshape a nib to your handwriting for a fee, and a long tradition of writing to strangers. Pens are discussed by maker and model, and the conversation is usually about the nib — its width, its flex, and how wet it writes — rather than the body. There are two distinct markets. Modern limited editions, dominated by Montblanc\'s numbered series, are bought as collectibles and often never inked. Vintage pens from the 1920s–1950s (Parker, Waterman, Pelikan) are bought to be used and restored, and have their own repair culture around replacing perished sacs and adjusting nibs. Japanese makers occupy their own tier, prized for lacquer work — maki-e — applied by named artists over many months.',
    glossary: [
      { term: 'Nib', definition: 'The writing tip, and most of what you are paying for. Gold nibs (14k, 18k) flex and feel different from steel; the width (EF, F, M, B) changes the pen completely.' },
      { term: 'Limited edition (LE)', definition: 'A numbered run made once. Montblanc’s Patron of Art and High Artistry lines are the ones that carry serious money — the Victoria 888 in our catalogue is about €161,220.' },
      { term: 'Maki-e', definition: 'Japanese lacquer decoration, applied and polished by hand over many layers. It is why a Namiki Emperor Dragon sits near €12,700.' },
      { term: 'Filling system', definition: 'How ink gets in — cartridge, converter, piston or vintage sac. It matters for collecting because old sacs perish and need replacing.' },
    ],
    care:
      'Flush a pen you actually use with cool water and never leave ink to dry in it — a dried nib and feed is the most common damage on a second-hand pen. Store pens horizontally or nib-up; nib-down leaks. Keep celluloid and lacquer out of sunlight and away from heat, both of which discolour them permanently. If a vintage pen has a hardened ink sac, have it re-sacced by a restorer rather than forcing the filler.',
    watchOut: {
      title: 'Frankenpens and swapped nibs',
      body: 'At these prices, parts get mixed. A pen assembled from several donors, or fitted with a nib from a different model, is worth far less than either original — and it is not obvious in a photograph. Ask for a picture of the nib imprint and the barrel imprint together, check the numbering on a limited edition against the certificate and box, and be careful with "restored" vintage pens that do not say what was replaced.',
    },
    valueDrivers:
      'Limited edition status above all: Montblanc dominates the top of this market, and the Patron of Art and High Artistry series account for almost every four- and five-figure pen we track. Then materials and craft — solid gold, maki-e lacquer, hand engraving. Then completeness: box, papers and the numbered certificate are a large part of the value on an LE. Condition matters, but a well-used pen from a great edition still outsells a mint one from an ordinary line.',
    holyGrail: {
      title: 'Montblanc Patron of Art Victoria 888',
      why: 'About €161,220 — the single most valuable item in the entire app, not just this category. A tiny numbered run in precious metal from Montblanc’s flagship series, which is what happens when a luxury house builds an object specifically for people who collect.',
    },
    entryLevel: {
      title: 'A steel-nib pen from a serious maker (Lamy, TWSBI, Pilot)',
      why: 'Well under the €300 median, and the right first purchase: they write beautifully, they are built to be flushed and refilled for years, and they teach you what nib width and filling system you actually like before you spend real money on an edition.',
    },
  },

  lego: {
    intro:
      'LEGO is the largest non-card collecting market in the app. Almost all of it is affordable — half the sets we track are under €30 — and the value sits in a narrow band of retired sets, convention exclusives and the very old.',
    whatItIs:
      'LEGO\'s collecting culture is organised around the set, not the brick. Every set has a number — 10276, 75192 — and collectors talk in those numbers because names are ambiguous and get reused. It is the largest non-card catalogue in this app, and unlike the card games almost all of it is affordable: half the sets we track are under €30.\n\nThe mechanism that governs value is retirement. LEGO produces a set for a couple of years and then stops, permanently, and retirement is the event everything revolves around. There is an entire practice of buying sets at retail shortly before production ends, which is the only reliably "cheap" entry into the appreciating end of this hobby. Before retirement you are competing with a factory that can make more; after it, supply only shrinks.\n\nThe adult side of the hobby is served openly by LEGO itself, and knowing the lines saves a beginner a lot of confusion. Modular Buildings are released roughly one a year and designed to connect into a street, which is why collectors chase complete runs. Ultimate Collector Series (UCS) are the large Star Wars display models. Creator Expert covers the rest of the adult-targeted sets. Those three hold value in a way licensed juvenile sets simply do not.\n\nTwo more things a beginner needs. Condition vocabulary here is about the box as much as the bricks: MISB (mint in sealed box) is the premium version of any set, CIB (complete in box) means opened but complete, and a set with its stickers already applied is worth less than one with them unused on the sheet. And the real scarcity is not retail at all — convention exclusives like The Collector (SDCC 2014, ~€1,190) and Inside Tour sets given only to people who visit the factory in Billund (~€6,996) were made in a few hundred copies and never sold normally.',
    glossary: [
      { term: 'MISB / sealed', definition: 'Mint In Sealed Box: never opened, factory seals intact. The premium version of any set, and the one most affected by storage damage.' },
      { term: 'CIB / complete', definition: 'Complete In Box: opened and built, but all parts, instructions and box present. Worth far less than sealed and far more than loose bricks.' },
      { term: 'Retired', definition: 'A set LEGO has stopped producing. Retirement is the single event that starts a set appreciating — before it, you are competing with a factory.' },
      { term: 'UCS', definition: 'Ultimate Collector Series — the large, display-oriented Star Wars sets. Consistently the strongest Star Wars performers; the UCS AT-AT is about €996 in our catalogue.' },
    ],
    care:
      'Sealed sets are damaged by the things nobody thinks about: sunlight yellows white and grey bricks through the box, damp lifts the flaps, and stacking crushes corners. Store boxes upright, flat-side down, somewhere dry and dark. For built sets, dust is the enemy of display value and stickers are the enemy of resale — a set with stickers applied is worth less than the same set with them unused in the sheet.',
    watchOut: {
      title: 'A "sealed" box is not always sealed',
      body: 'Resealing is a real trade: a box is opened, parts removed or swapped, and the flaps re-glued. Buy sealed sets from sellers who show the factory seals close up, and be sceptical of an old set that looks too clean. The second trap is clone brands — near-identical copies of retired sets sold with convincing boxes, which are worth nothing to a collector.',
    },
    valueDrivers:
      'Retirement first: a set only starts climbing once it is out of production. Then theme — Star Wars UCS, Modular Buildings and Creator Expert hold value in a way licensed juvenile sets do not. Then exclusivity: convention sets are the real scarcity, with The Collector (SDCC 2014) at about €1,190 and Steve Rogers Captain America (SDCC 2016) at €1,060, both made in a few hundred copies. Then condition of the box, then minifigures, which can carry a large share of a set’s price on their own.',
    holyGrail: {
      title: 'LEGO Inside Tour Anniversary Collection',
      why: 'About €6,996, the most expensive LEGO item we track. Inside Tour sets are given only to people who attend LEGO’s own factory tour in Billund — they are never sold, which is the purest form of scarcity in this hobby. The €5,650 Ferguson Tractor makes the other case: it is simply very old and almost nobody kept the box.',
    },
    entryLevel: {
      title: 'A set you actually want, bought just before it retires',
      why: 'The median set we track is under €30. Buying at retail shortly before retirement is the only reliable "cheap" entry, and unlike most categories the downside is a box of LEGO you like. Modulars and UCS sets are the ones worth watching for retirement announcements.',
    },
  },

  retro_games: {
    intro:
      'Retro game collecting spans loose cartridges worth a couple of euros and sealed rarities worth six figures. The median game we track is €68 — but this is a category where a single box can be worth more than a house deposit.',
    whatItIs:
      'Retro game collecting is organised by console generation, and each console has its own culture, prices and fakes. The hobby\'s fault line is between people who play their games and people who never will: a sealed, graded copy of a game is a different object from a working cartridge, sold to a different buyer at a different price. Region matters more than newcomers expect — a Japanese Super Famicom game will not run in a European SNES, and Japanese copies are often much cheaper for the same title. Three-letter shorthand does most of the talking in listings: CIB (complete in box), loose, sealed. And the community has a long memory for the specific rarities — Stadium Events, Little Samson, the Neo Geo library — which is why those names carry a premium the games themselves do not always justify.',
    glossary: [
      { term: 'CIB', definition: 'Complete In Box — cartridge, box and manual together. The standard collecting condition, and usually several times the loose price.' },
      { term: 'Loose', definition: 'The cartridge or disc alone. How most retro games trade, and where a beginner should start.' },
      { term: 'Repro', definition: 'A reproduction cartridge: a modern board and shell built to look like a rare original. The defining fraud of this category.' },
      { term: 'Region (NTSC / PAL / JP)', definition: 'Games were released regionally and are not interchangeable. Japanese releases are often far cheaper — or, occasionally, far rarer.' },
    ],
    care:
      'Keep cartridges out of damp — the contacts corrode and the label lifts. Cardboard boxes are the fragile part of any CIB game and should be stored upright and supported, never with weight on them. Battery-saved carts (Zelda, Pokémon, most RPGs) have a lithium cell inside that eventually dies; it can be replaced, but a leaking one damages the board, so do not leave a dead battery in a valuable cartridge.',
    watchOut: {
      title: 'Reproduction cartridges are everywhere, and they are good',
      body: 'Every expensive NES and SNES game has been reproduced — Little Samson and Hagane especially. Tells are a too-clean label, wrong shell screws (a genuine Nintendo cart needs a security bit), a glossy modern label print and a board with a modern chip. Buy expensive carts from specialists, ask for a photo of the board, and be very careful with sealed and graded games: the grading boom brought resealing with it.',
    },
    valueDrivers:
      'Completeness and condition first — loose to CIB to sealed roughly multiplies the price at each step, and graded sealed copies are their own market. Then genuine rarity: Stadium Events is expensive because almost all copies were recalled, not because it is a good game. Then platform, with Neo Geo AES commanding prices no other console does (Kizuna Encounter at about €4,995). Then region and demand — EarthBound CIB at €2,163 is scarcity meeting a devoted audience.',
    holyGrail: {
      title: 'Stadium Events, complete in box (NES)',
      why: 'About €104,987 — the most expensive game in our catalogue and one of the most famous in the hobby. Nintendo pulled and rebranded it almost immediately, so very few boxed copies exist. It is the clearest example of the rule here: recalls and mistakes create value, popularity does not.',
    },
    entryLevel: {
      title: 'Loose carts for a console you owned',
      why: 'Common loose games cost a few euros and still play. Buy the console you actually grew up with, buy loose, and only move to CIB once you know which games you want to keep — the box is most of the price and none of the fun.',
    },
  },

  watches: {
    intro:
      'Watch collecting is the highest-value category in the app after fountain pens: the typical watch we track is about €2,350, and the top of the market runs past €400,000. It rewards patience and research more than any other category here.',
    whatItIs:
      'Watch collecting has its own vocabulary and its own etiquette, and both are worth learning before you spend. Watches are discussed by reference number rather than by name, because "Submariner" describes dozens of watches worth wildly different amounts. The hobby\'s central value is originality: an unpolished case, the dial it left the factory with, and the box and papers that came with it. Collectors talk about "patina" — the way old dials and lume age to cream or brown — as a virtue rather than a defect, which is why a faded dial can be worth more than a perfect one. There is a strong culture of independent watchmaking (F.P. Journe, Richard Mille) sitting alongside the historic Swiss houses, and a very active enthusiast press and forum world where models are argued about for decades. Almost nothing here is bought on impulse.',
    glossary: [
      { term: 'Reference number', definition: 'The manufacturer’s model code, stamped between the lugs or on the caseback. It identifies the exact variant — and variants of the same model can differ enormously in price.' },
      { term: 'Full set', definition: 'Watch, box, papers, and ideally the original receipt and spare links. A full set is worth meaningfully more than the identical watch alone.' },
      { term: 'In-house movement', definition: 'A movement the brand designed and makes itself, rather than buying in. A large part of what separates a €2,000 watch from a €200,000 one.' },
      { term: 'Redial', definition: 'A dial that has been repainted. It destroys collector value on a vintage piece even when it looks better than the original.' },
    ],
    care:
      'Service a mechanical watch every five years or so, and keep the paperwork — service history is part of the value. Do not let anyone polish the case "to tidy it up": polishing rounds off the factory edges permanently and is one of the few irreversible ways to lose thousands. Keep watches away from magnets, store them out of direct sun (dials fade), and if a vintage piece is not water-resistant any more, treat it as if it never was.',
    watchOut: {
      title: 'Frankenwatches, redials and superfakes',
      body: 'At these prices the fraud is sophisticated. A frankenwatch is assembled from parts of several — correct-looking, wrong-value. Superfake Rolex and AP now fool casual inspection, including weight and movement decoration. Buy from an established dealer or with an authentication service, insist on the reference number matching the papers, and be suspicious of a "rare dial" that no reference book shows.',
    },
    valueDrivers:
      'Brand and model first — Patek Philippe, Audemars Piguet, Richard Mille and F.P. Journe occupy the entire top of our catalogue, and a Royal Oak or Nautilus is a different market from the rest of the brand. Then originality: unpolished case, original dial and hands, matching papers. Then production numbers and the story — the Cartier Crash at about €418,240 is a strange, tiny-production design, not a technical achievement. Condition and service history sit under all of it.',
    holyGrail: {
      title: 'Cartier Crash (WGCH0080)',
      why: 'About €418,240, the most valuable watch we track. Cartier has made it in very small numbers since the 1960s and its warped case makes it instantly recognisable — proof that in watches, design scarcity can outrun complication and precious metal entirely.',
    },
    entryLevel: {
      title: 'A serviced vintage Seiko, Citizen or a modern microbrand',
      why: 'Far below the €2,350 median, mechanically honest, and cheap enough to learn on. You will make your early mistakes — a redial, an over-polished case, a missing box — and it is much better to make them at €200 than at €20,000.',
    },
  },

  retro_pokemon: {
    intro:
      'Vintage Pokémon is a separate market from modern Pokémon, with different risks and prices two orders of magnitude apart. The typical card we track here is about €192 — and the ceiling is €129,679.',
    whatItIs:
      'Roughly, Pokémon cards printed before the modern era, and in practice three groups. The Wizards of the Coast years (1999–2003) produced Base Set, Jungle, Fossil and the rest, printed in the middle of a craze by children who played with them — which is why survivors in good condition are scarce. The e-Card and EX era that followed introduced Gold Star cards, an ultra-rare treatment with a gold star beside the name. And running alongside both, Black Star Promos handed out at events and through magazines in tiny numbers. Knowing which era a card belongs to tells you more about its price than the Pokémon on it does.',
    glossary: [
      { term: '1st Edition', definition: 'A small stamp on the left of the artwork, applied only to the first print run of a set. It can multiply a card’s value several times over the identical unlimited version.' },
      { term: 'Shadowless', definition: 'Very early Base Set cards printed without the drop shadow on the right of the art box. Rarer than the normal unlimited version — a PSA 10 Shadowless Charizard is about €52,324 in our catalogue.' },
      { term: 'Gold Star', definition: 'A 2003–2007 ultra-rare treatment marked with a gold star. Mewtwo, Pikachu and Rayquaza Gold Stars are the top of our vintage catalogue at €60,000–€130,000.' },
      { term: 'Black Star Promo', definition: 'Event and magazine promos outside the numbered sets. The Lily Pad Mew #47 sits around €62,992.' },
    ],
    care:
      'Anything you believe is genuinely vintage and valuable should be in a penny sleeve and a rigid holder before you do anything else with it, including showing it to somebody. Never clean a vintage card — no erasers, no solvents, no "just the edges". Keep cards out of daylight; the Base Set holo foil fades and cannot be restored. If a card is worth more than the grading fee, graded and slabbed is the safest way to store and later sell it.',
    watchOut: {
      title: 'Fakes, and worse, tampered slabs',
      body: 'Vintage Pokémon is the most counterfeited collectible in this app. Beyond outright fakes, the specific vintage risks are trimming (shaving a card’s edges to fake a better grade) and pressing (flattening it under heat). Both are invisible to a beginner and both are why cards at this level are bought in third-party slabs — and why you should check a slab’s certification number against the grader’s own database before paying, because counterfeit slabs exist too.',
    },
    valueDrivers:
      'Grade above everything: the same card is a different asset at PSA 9 and PSA 10, and our two most expensive Charizards are both graded 10. Then era markers — 1st Edition and Shadowless status. Then the treatment: Gold Star and promo scarcity. Then the Pokémon, with Charizard, Pikachu and Mewtwo commanding premiums no other character gets.',
    holyGrail: {
      title: 'Gold Star Mewtwo (EX Holon Phantoms #103)',
      why: 'About €129,679, the most valuable card in our vintage catalogue — ahead of even a PSA 10 1st Edition Base Set Charizard at €124,529. Gold Stars were pulled at roughly one in every few booster boxes, and almost nobody protected them at the time.',
    },
    entryLevel: {
      title: 'Unlimited-era commons, uncommons and played holos',
      why: 'The same sets everyone wants, without the 1st Edition stamp or the grade. A played Base Set holo is affordable, unmistakably vintage, and cannot be ruined by anything you do to it — the ideal way to learn what real cards feel like before you spend serious money.',
    },
  },

  disney: {
    intro:
      'Disney collecting is unusually broad: park exclusives, pin trading, luxury collaborations and original production artwork all sit in one category. The typical item we track is about €52, and the top is one-of-a-kind studio art.',
    whatItIs:
      'Disney collecting is unusually social, and much of it happens inside the parks. Pin trading is the clearest example: guests buy pins, wear them on lanyards, and trade with staff and each other under an etiquette where a cast member must accept any trade offered. Merchandise is released constantly, tied to park anniversaries, films and seasons, and a great deal of it is exclusive to one park or one year — which is where scarcity comes from, since Disney rarely reissues. Around that sits a much older and more serious market in studio artwork: production cels and sketches from the hand-drawn era, when every frame was painted on celluloid, each one unique. The two ends barely resemble each other, but they sit in one category because the affection driving them is the same.',
    glossary: [
      { term: 'Production cel', definition: 'A hand-painted sheet of celluloid actually photographed for a film. Each one is unique, which is why a Dumbo "Pink Elephants" cel is about €2,544.' },
      { term: 'Scrapper', definition: 'A pin made from rejected or unauthorised factory runs. Superficially identical to an official pin, worthless to a trader.' },
      { term: 'Park exclusive', definition: 'Merchandise sold only inside the parks, often for one season. Designer Ears — the Heidi Klum pair is around €4,386 — are the extreme case.' },
      { term: 'Limited Edition (LE) / Limited Release (LR)', definition: 'LE means a stated number was made and it is stamped on the item. LR just means "for a while", which is a much weaker promise.' },
    ],
    care:
      'Original artwork and cels are the fragile part: keep them framed with UV glass, away from heat, and never trim or re-mount an original. Pins should be stored on a board or in a pin bag rather than loose in a tin, where the enamel chips. Plush and fabric ears fade badly in sunlight, and vinyl figures warp in a hot car — the two most common ways park merchandise is ruined on the way home.',
    watchOut: {
      title: 'Pin trading is full of fakes, and art is full of unverified provenance',
      body: 'Scrapper pins circulate in enormous numbers and are sold in bulk lots as genuine; tells are rough edges, wrong pin backs, blurry printing and colour bleed. At the other end, "original production art" without documented provenance is worth a fraction of an authenticated piece — for cels and sketches, buy from a recognised gallery or auction house with paperwork, not from a photograph.',
    },
    valueDrivers:
      'Uniqueness first: production art is one of one, which is why the Bambi sketch at €14,793 sits above everything else. Then genuine limitation — a numbered LE run beats an open "limited release". Then licensed luxury collaborations (Swarovski, Montblanc, Gucci) which carry the partner brand’s value as well as Disney’s. Then character and film, with the older animated classics ahead of most modern properties.',
    holyGrail: {
      title: 'Walt Disney Archives Bambi original sketch',
      why: 'About €14,793 — the most valuable Disney item we track. Original studio artwork cannot be reprinted, reissued or restocked, which puts it in a different category from every other kind of Disney merchandise.',
    },
    entryLevel: {
      title: 'Open-edition pins and current park merchandise',
      why: 'Half of what we track is under €52, and pins are the classic entry: cheap, tradable in the parks, and a genuinely social way in. Just buy from the parks or Disney directly at first, until you can spot a scrapper.',
    },
  },

  hot_toys: {
    intro:
      'This is the high-end end of collectible figures: sixth-scale figures, quarter-scale statues and life-size busts from Hot Toys, Sideshow, Prime 1 and Queen Studios. The typical piece is about €53, but the serious ones run into thousands.',
    whatItIs:
      'Two different objects share this shelf. A sixth-scale figure is an articulated, rooted-hair, real-fabric-costume replica of a film character about 30cm tall — Hot Toys is the brand that made this a category. A statue is not articulated at all: a fixed polystone or resin sculpture, usually larger, made to be looked at. Both are licensed, both are produced in limited runs announced months in advance, and both are largely bought on preorder — you pay before the thing exists, which is a collecting habit worth understanding before you adopt it.',
    glossary: [
      { term: 'Sixth scale (1/6)', definition: 'The standard for articulated collectible figures — roughly 30cm, with cloth clothing and interchangeable hands and heads.' },
      { term: 'Polystone', definition: 'The heavy resin-and-stone composite most statues are cast in. It takes fine detail beautifully and chips if you drop it.' },
      { term: 'Exclusive edition', definition: 'A version with extra parts sold only through one retailer or the maker’s own site. It reliably outsells the standard edition of the same piece.' },
      { term: 'Preorder', definition: 'Paying up front, often a year ahead of release. Standard practice here, and the main way money gets tied up in this category.' },
    ],
    care:
      'Keep everything out of direct sunlight and away from radiators: sixth-scale figures have rubber and soft-goods parts that yellow, harden and eventually crack, and heat is what does it. Do not leave a figure posed under its own weight for years — joints sag and costumes crease permanently. Keep the box and the inner tray; for statues especially, a piece without its shipper is much harder to sell and much easier to break in transit.',
    watchOut: {
      title: 'Preorder culture and unlicensed recasts',
      body: 'Two traps. First, preorders: money committed a year ahead, on a piece whose value at release is unknowable, and cancellations are not always refundable — never preorder more than you would happily own at full price. Second, recasts: unlicensed copies of statues cast from originals, common at the high end, with soft detail and poor paint. Buy statues from authorised dealers, and check the edition number and certificate.',
    },
    valueDrivers:
      'Edition size and exclusivity first, then the licence — Marvel, Star Wars and DC hold value more reliably than one-film properties. Scale and format matter enormously: life-size busts and quarter-scale statues top our catalogue, with the Iron Man Mark XLIII life-size bust at about €5,390 and the Ghostbusters Ecto-1 sixth-scale vehicle at €4,789. Condition of both piece and box, and whether it is the exclusive version, decide the rest.',
    holyGrail: {
      title: 'Iron Man Mark XLIII Life-Size Bust (Sideshow)',
      why: 'About €5,390 — the top of our catalogue here. Life-size pieces are made in tiny numbers because almost nobody has the room, which makes them scarce for a reason that has nothing to do with demand.',
    },
    entryLevel: {
      title: 'A single sixth-scale figure of a character you love, bought in stock',
      why: 'Half of what we track is under €53. Buying something already released, rather than preordering, means you see the reviews, the real paint applications and the real price before you commit — and one good figure teaches you more than three preorders.',
    },
  },

  gunpla: {
    intro:
      'Gunpla are Bandai’s Gundam model kits. They are designed to be built without glue or paint, and the whole hobby is unusually affordable: the typical kit we track is €67, and even the flagship kits stop around €750.',
    whatItIs:
      'Snap-fit plastic model kits of the mecha from the Gundam anime. The parts come on runners in colour-separated plastic, so a kit looks finished straight off the sprue — no paint required, though people do paint them. Kits come in grades that describe size and complexity rather than quality: HG (High Grade, 1/144, the cheap and quick one), RG (Real Grade, 1/144 but far more detailed), MG (Master Grade, 1/100, with an inner frame), and PG (Perfect Grade, 1/60, the flagship). Separately, Metal Build is not a kit at all — it is a pre-assembled die-cast figure sold at kit-adjacent prices, which is why it appears in the same list.',
    glossary: [
      { term: 'HG / RG / MG / PG', definition: 'The grades, cheapest and simplest to largest and most complex. An HG is an evening; a PG is a project.' },
      { term: 'P-Bandai', definition: 'Bandai’s web-exclusive line — kits sold only online, in one production window, never restocked. This is where most Gunpla scarcity comes from.' },
      { term: 'Nub marks', definition: 'The small blemishes left where a part was cut from the runner. Cleaning them up is the basic skill of the hobby, and visibly poor nub removal reduces a built kit’s resale value.' },
      { term: 'Panel lining', definition: 'Running a fine pen or wash into the recessed lines so detail reads at a distance. The cheapest way to make a kit look finished.' },
    ],
    care:
      'Built kits are damaged mainly by sunlight and gravity: UV yellows white plastic permanently, and heavy posed arms slowly loosen their joints, so display them relaxed rather than dramatic. Sealed kits are simple — keep the box dry and unsquashed. If you use panel-lining pens or top-coat sprays, test on a runner first; solvent-based products can craze the plastic and there is no undoing it.',
    watchOut: {
      title: 'Bootleg kits and the P-Bandai scramble',
      body: 'Unlicensed copies ("KO" kits) are sold at a discount with copied box art. The plastic is softer, the colours are off, and the fit is poor — check for Bandai’s logo and holographic seal, and be suspicious of a current kit far below normal retail. The other trap is P-Bandai: web exclusives sell out in one window and then only exist on the secondary market, which is where impulse buying at inflated prices happens.',
    },
    valueDrivers:
      'Grade first — PG and Metal Build occupy the whole top of our catalogue, with the PG Exia Lighting Model at about €753. Then whether it is discontinued or a P-Bandai exclusive, which is the only real scarcity here. Then sealed versus built: unlike statues, a well-built kit is worth much less than the same kit sealed, because anyone can build one. Then the design’s popularity, where the Exia, Wing Zero and Nu Gundam do the heavy lifting.',
    holyGrail: {
      title: 'PG Exia (Lighting Model)',
      why: 'About €753 — the flagship Perfect Grade with the LED lighting set built in. Note how low that ceiling is compared with other categories in this app: Gunpla is a hobby about building, not about scarcity, and the prices reflect it.',
    },
    entryLevel: {
      title: 'An HG or RG kit of a design you like',
      why: 'Well under the median, buildable in an evening or two with nothing but a cheap nipper, and genuinely fun. Buy the mobile suit you think looks best — every experienced builder will tell you the same thing.',
    },
  },

  action_figures: {
    intro:
      'Mainstream collectible action figures — NECA, Mezco, Hasbro, Bandai’s S.H.Figuarts and Jazwares. It is one of the most affordable categories in the app: half of what we track is under €34, and the ceiling is a few hundred euros.',
    whatItIs:
      'The modern collectible figure hobby is not the toy aisle, even though it looks like it. Figures are made in dedicated adult lines — NECA for horror and film licences, Mezco\'s ONE:12, Bandai\'s S.H.Figuarts — with high articulation, interchangeable hands and faces, and prices to match. The hobby splits sharply on packaging: a "carded" collector never opens anything and stores figures in protective cases, while an "opener" displays them posed and considers the box disposable. That single decision changes what you buy and what it is worth later. Releases are announced at conventions months ahead, sold partly on preorder, and specific figures are made exclusive to one retailer or one show — which is where the scarcity in an otherwise mass-produced category comes from.',
    glossary: [
      { term: 'MOC / carded', definition: 'Mint On Card — still sealed in its original packaging. For collectors this is usually worth several times a loose figure of the same character.' },
      { term: 'Loose', definition: 'Out of the packaging. How most figures trade, and the sane way to actually enjoy them.' },
      { term: 'S.H.Figuarts (SHF)', definition: 'Bandai’s highly-articulated line, strong on Kamen Rider, Dragon Ball and Star Wars. The Den-O figure is about €266 in our catalogue.' },
      { term: 'ONE:12', definition: 'Mezco’s premium sixth-scale-adjacent line with cloth costumes and heavy articulation — the Ghostbusters set sits near €344.' },
    ],
    care:
      'If you are keeping figures carded, the card and bubble are the entire value: store them upright in protective cases, never stacked, and keep them out of sunlight because the bubble yellows and the cardboard fades. Loose figures suffer from joint stress — do not leave one in an extreme pose for years, and be careful with tight new joints, which snap rather than bend when cold. Keep accessories in a labelled bag; a loose figure missing its parts is worth a fraction of a complete one.',
    watchOut: {
      title: 'Reproduction cards and invented "exclusives"',
      body: 'Reproduction packaging for older figures is easy to buy, so a "carded vintage" figure may be a loose figure on a new card — check the card stock, the print quality and whether the bubble has been reglued. Also treat the word "exclusive" carefully: convention and retailer exclusives are real and carry a premium, but the term is used loosely in listings for figures that were simply sold in one shop.',
    },
    valueDrivers:
      'Packaging condition first if carded, then whether the line is discontinued — NECA’s licensed horror figures hold value well, with Leatherface at about €473. Then genuine exclusivity, then licence popularity, then completeness of accessories. This is a category where condition and completeness matter more than rarity: almost nothing here was made in small numbers, so what survives intact is what commands the price.',
    holyGrail: {
      title: 'NECA Leatherface (Texas Chainsaw Massacre, 1974)',
      why: 'About €473, the top of our catalogue here. Worth noticing how modest that is — this is the most accessible collecting category in the app, and the "grail" is a figure a normal person could decide to buy.',
    },
    entryLevel: {
      title: 'Loose figures from a line you already like',
      why: 'Loose examples of the same figures cost a fraction of carded ones and are far more fun to own. Start loose, decide whether you actually care about packaging, and only then pay the carded premium.',
    },
  },

  comic_books: {
    intro:
      'Comic collecting is the oldest of these hobbies and the one where grading matters most. The typical book we track is about €71 — and a first appearance in high grade runs to five figures.',
    whatItIs:
      'Comic collecting is the oldest of these hobbies and has the most developed language. Books are identified by title, issue number and printing, and the market divides into "ages" — Golden (1938–56), Silver (1956–70), Bronze, and Modern — which describe both era and expectations of condition. Nearly all value concentrates in "keys": issues where something happened for the first time, above all a character\'s first appearance. Since 2000 the hobby has been reshaped by third-party grading, and a graded book in a sealed slab is now the default way expensive comics change hands. Two consequences follow: the physical experience of reading is separated from ownership entirely, and film casting news moves prices within hours, because a character\'s first appearance is a finite supply meeting a sudden audience.',
    glossary: [
      { term: 'Key issue', definition: 'A book that matters for a reason beyond the story: a first appearance, a first cover, a death. Almost all comic value lives in keys.' },
      { term: 'CGC / CBCS', definition: 'Third-party graders. They authenticate a book, grade it 0.5–10.0 and seal it in a slab. A grade of 9.6 versus 8.0 can be a multiple, not a percentage.' },
      { term: 'Slab', definition: 'The sealed holder a graded comic lives in. Cracking it out to read the book destroys the grade and most of the premium.' },
      { term: 'Variant', definition: 'An alternative cover for the same issue, often produced in far smaller numbers than the standard edition.' },
    ],
    care:
      'Bag and board everything, use acid-free boards, and replace them every few years — the board is what goes acidic and yellows the book it is protecting. Store boxes upright in a cool, dry place off the floor, never in a loft or a garage where heat and damp cycle. Do not tape, trim, colour-touch or press a book yourself: undisclosed restoration is treated as damage by graders and buyers alike.',
    watchOut: {
      title: 'Restoration, married copies and trimmed edges',
      body: 'A cleaned, pressed or colour-touched book is worth far less than a clean one, and it is very hard to see in a photo. So is a "married" copy — a book completed with pages or a cover from another copy. This is precisely why expensive keys are bought graded: the slab is not snobbery, it is the only practical authentication. If you buy raw, buy from someone who states restoration explicitly.',
    },
    valueDrivers:
      'First appearance above all — Amazing Fantasy #15 is the first Spider-Man, which is why a CGC 4.0 sits at about €35,529 despite being a mid grade. Then grade, then the character’s current cultural weight, which film and television move sharply. Age matters, but a 1940s book nobody wants is cheaper than a 1974 Hulk #181 (first Wolverine, about €11,838). Signature series and pedigree collections add a further premium.',
    holyGrail: {
      title: 'Amazing Fantasy #15 — first appearance of Spider-Man (CGC 4.0)',
      why: 'About €35,529 in our catalogue, and note the grade: 4.0 is a well-read copy. When a book is important enough, condition stops being the gate — presence is. That is the opposite of how nearly every other category in this app works.',
    },
    entryLevel: {
      title: 'Modern keys and reader copies of older books',
      why: 'Half of what we track is under €71. Recent first appearances cost cover price and occasionally become something; low-grade copies of famous older issues let you own the actual book for a fraction of slab money. Both are better first buys than a mid-grade slab of something you have not read.',
    },
  },

  sneakers: {
    intro:
      'Sneaker collecting is driven by limited releases and designer collaborations. The typical pair we track is about €126, and the collaborations at the top run past €14,000.',
    whatItIs:
      'Sneaker collecting runs on release mechanics as much as on shoes. Limited pairs are sold through timed online draws and app raffles, which means buying at retail is mostly luck and the secondary market is where most pairs actually change hands. The hobby\'s vocabulary is compact: deadstock means unworn with everything included, a "colourway" is a specific colour version of a silhouette, and "hype" is used plainly to describe demand that is not about the shoe. Collaborations drive the whole top of the market — an artist, designer or fashion house puts their name on a Jordan or an Air Force 1 and the price multiplies. The unavoidable physical fact underneath all of it is that shoes decay: foam and glue break down over a decade or so whether the pair is worn or not, which makes this the only category here where the object has a shelf life.',
    glossary: [
      { term: 'Deadstock (DS)', definition: 'Never worn, with the original box and all inserts. The standard condition for resale — anything else is priced far below it.' },
      { term: 'Collaboration', definition: 'A release designed with an outside brand or person. These occupy the entire top of our catalogue: Travis Scott, Dior, Louis Vuitton, Tiffany & Co.' },
      { term: 'General release (GR)', definition: 'A normal, unlimited release you can buy in shops. Sells for retail or below, and is where most people should start.' },
      { term: 'Legit check', definition: 'Having a pair authenticated. Common practice, and necessary at these prices.' },
    ],
    care:
      'The material is the problem: polyurethane midsoles hydrolyse and crumble with age whether you wear them or not, so a decade-old deadstock pair may be unwearable regardless of storage. Keep pairs out of heat and damp, out of sunlight (which yellows midsoles), and use silica gel in the box. Do not vacuum-seal them — they need some air. Accept that in this category the object is decaying, which is not true of a card or a coin.',
    watchOut: {
      title: 'Fakes are the industry, not the exception',
      body: 'Hyped models are counterfeited at enormous scale, and the good fakes now copy stitching, box labels and even the receipt. Buy from a platform that authenticates, or have the pair legit-checked before money moves. Be especially careful with the luxury collaborations at the top of this market — Louis Vuitton and Dior Jordans are among the most faked objects in collecting.',
    },
    valueDrivers:
      'Collaboration and limitation first, by a wide margin: our top pairs are the Travis Scott Jordan 4 at about €14,472 and the Tiffany & Co. Air Force 1 at €13,157. Then size — the same pair varies in price by size, unlike almost anything else in this app. Then deadstock condition and a complete box. Then the model’s standing, with Jordan 1 and Air Force 1 outperforming most silhouettes.',
    holyGrail: {
      title: 'Air Jordan 4 Travis Scott (Purple)',
      why: 'About €14,472 — a small, hyped collaborative release, which is now the only reliable way a mass-produced shoe reaches five figures. Vintage rarity barely exists here, because old sneakers mostly fall apart.',
    },
    entryLevel: {
      title: 'General releases in your own size',
      why: 'Half of what we track is under €126, and general releases sit at or below retail. Buy something you will actually wear: given hydrolysis, a pair that is worn and enjoyed loses less real value than a pair that quietly disintegrates in a box.',
    },
  },

  funko: {
    intro:
      'Funko Pops are cheap, endlessly varied vinyl figures — the typical one we track is €22 — with a small number of convention exclusives and early figures that reach four figures.',
    whatItIs:
      'Funko Pops are a deliberately uniform format — same body, same oversized head, same blank stare — applied to essentially every licence in existence, and that sameness is the point: the fun is in the breadth of what exists. The company releases thousands of figures a year and numbers each one within its licence, which is how collectors refer to them ("#10 Vegeta"). Value comes from three places only: convention exclusives handed out in small numbers, "chases" seeded roughly one per case, and figures old enough to predate Funko\'s enormous scale-up. Everything else is a mass-produced object worth roughly what it cost. The community is large, friendly and heavily focused on display, and the box is treated as part of the item, which is why protective cases are standard rather than eccentric.',
    glossary: [
      { term: 'Vaulted', definition: 'Retired by Funko and no longer produced. The event that starts a Pop appreciating, if it ever does.' },
      { term: 'Chase', definition: 'A rarer variant of a figure (a glow, a flock, a different pose) inserted into roughly one in six cases, marked with a sticker on the box.' },
      { term: 'Freddy Funko', definition: 'The company’s own mascot, dressed as other characters and given out at conventions in tiny numbers. Three of the five most expensive Pops we track are Freddy Funkos.' },
      { term: 'Box condition', definition: 'For Pops the box is most of the value: creases, shelf wear and sun fading matter more than the figure inside, which is nearly indestructible.' },
    ],
    care:
      'Keep boxes out of direct sunlight — the printing fades quickly and a faded box halves the value of an otherwise mint figure. Use hard plastic protectors for anything you care about, store upright, and keep them off radiators, since vinyl warps. If you display them out of box, accept that you have taken most of the resale value off the table and enjoy them instead.',
    watchOut: {
      title: 'Almost none of them go up, and fake stickers are easy',
      body: 'Funko has produced tens of thousands of figures in huge quantities; the overwhelming majority will never be worth more than retail, and buying Pops as an investment is the classic beginner mistake in this category. Where money is involved, exclusive stickers (SDCC, ECCC, Chase) are trivially reproduced and routinely applied to common figures — check the sticker’s print quality and the figure’s actual production details, not just the label.',
    },
    valueDrivers:
      'Genuine convention scarcity first: the Freddy Funko exclusives given away at SDCC in a few hundred pieces are the top of the market, with Freddy as Boba Fett at about €4,661. Then early, long-vaulted figures with low numbers — Planet Arlia Vegeta #10 is around €6,140. Then chase variants, then box condition. Character popularity matters far less here than production numbers.',
    holyGrail: {
      title: 'Planet Arlia Vegeta #10',
      why: 'About €6,140 — an early, short-run Dragon Ball figure from before Funko scaled up. It is the clearest illustration of the category’s rule: what makes a Pop valuable is having been made in 2013, not being popular in 2026.',
    },
    entryLevel: {
      title: 'Any Pop of a character you like, at retail',
      why: 'Half of what we track is under €22 and most Pops are freely available. Buy the ones you want to look at. Treat the occasional vaulted figure that appreciates as a bonus rather than a plan.',
    },
  },

  sportscards: {
    intro:
      'Sports cards are the oldest and largest collectibles market of them all, and the most professionalised — grading, population reports and auction records shape every price. The typical card we track is €112, and the top is €526,362.',
    whatItIs:
      'Cards printed by a licensed manufacturer showing real athletes, sold in packs since the 1950s. Three names do most of the work: Topps (baseball, and historically everything), Panini (basketball and football since the 2010s) and Bowman (prospects — cards of players before they reach the top league). The single most important idea is the rookie card: a player\'s first licensed card, which is the one the market cares about for the rest of their career and beyond. Alongside that sits a modern industry of numbered parallels, autographs and memorabilia cards with a piece of a jersey embedded, all inserted at known odds. Because print runs and grading populations are published, this is the most quantified collecting market that exists — you can often look up exactly how many PSA 10s of a card are known to survive.',
    glossary: [
      { term: 'RC (rookie card)', definition: 'A player\'s first licensed card. Almost always the most valuable card of that player, regardless of what they do later.' },
      { term: 'Population report', definition: 'A grader\'s public count of how many copies exist at each grade. This is why sports cards price so precisely — supply at a given grade is a published number.' },
      { term: 'Parallel / numbered', definition: 'The same card in a different colour or finish, produced in a stated quantity ("/25"). The number printed on the card is the print run.' },
      { term: 'Auto / patch', definition: 'A card carrying a genuine signature, or a swatch of worn or game-used material. Both carry large premiums and both are heavily faked when unauthenticated.' },
    ],
    care:
      'Anything you might grade goes into a penny sleeve then a semi-rigid holder — not a hard toploader, which graders ask you to avoid for submissions. Keep cards away from light and humidity: colour on 1950s cardboard fades permanently, and a warped card cannot be flattened without it being detectable. Never clean, trim or press a card. For sealed wax, heat is the enemy — old gum and packs deteriorate, and a warped box loses most of its value.',
    watchOut: {
      title: 'Trimming, fake autos and counterfeit slabs',
      body: 'The vintage risk is alteration: a trimmed or pressed card that grades higher than it should, invisible to the naked eye. The modern risk is a forged signature with a worthless certificate. Both are why serious money moves in graded slabs from PSA, SGC or BGS — and why you should verify the slab\'s certification number on the grader\'s own site before buying, since counterfeit slabs exist and are convincing.',
    },
    valueDrivers:
      'Player first, and specifically their standing in the sport\'s history — a 1952 Topps Mickey Mantle at PSA 5 is €526,362 in our catalogue, and note the grade is only a 5. Then rookie status, then grade, then scarcity of the parallel. Modern cards add autograph and print run: a 2018 Bowman Chrome Shohei Ohtani autographed rookie sits at €68,923. Sealed vintage wax is its own market again, priced on the chance of what is inside.',
    holyGrail: {
      title: '1952 Topps Mickey Mantle',
      why: 'About €526,362 even in EX condition — the most valuable single item in this entire app. It is the card that made the hobby: Topps\' first Mantle, from a series where much of the unsold stock was famously dumped at sea, which is scarcity created by a business decision rather than by collectors.',
    },
    entryLevel: {
      title: 'Modern base cards and raw commons of players you follow',
      why: 'Half of what we track is under €112, and modern base cards cost cents. Buy raw, learn to spot centring and corner wear yourself, and only pay grading fees once you can predict the grade — the fee is fixed whether the card comes back a 10 or a 6.',
    },
  },

  vintage_toys: {
    intro:
      'Vintage toys — Kenner Star Wars, 1960s Barbie, pre-1990 playsets — are collected for objects that were made to be destroyed by children. The typical piece we track is €42; survivors in original packaging reach five and six figures.',
    whatItIs:
      'The market splits by line and by era, and the two dominant ones are Kenner\'s 1977–1985 Star Wars figures and Mattel\'s Barbie from 1959 onward. What makes them collectable is simple: they were cheap, mass-produced and played with, so the fraction that survived unopened is tiny and shrinking. Collectors talk in the language of the original retail — which card back a figure was sold on, which store had an exclusive, which running change happened mid-production. A "Last 17" Kenner figure means one of the final wave, released in small numbers as the line wound down. Packaging matters more here than in almost any other category, precisely because so little of it exists.',
    glossary: [
      { term: 'MOC / carded', definition: 'Mint On Card — never opened. For 1970s–80s figures this is the difference between tens and thousands of euros.' },
      { term: 'Card back', definition: 'Which version of the packaging a figure came on, usually counted by how many figures appear on the reverse. Same figure, different card back, very different price.' },
      { term: 'Store exclusive', definition: 'A set sold through one retailer only — the Sears Cloud City playset in our catalogue is about €3,476.' },
      { term: 'Repro', definition: 'A reproduction accessory, weapon or card. Extremely common for Kenner-era figures, and rarely disclosed.' },
    ],
    care:
      'Sunlight is the main enemy: it yellows white plastic and fades card backs permanently, and both are irreversible. Store carded figures upright in acrylic cases, away from heat, never in a loft. Loose figures lose their tiny accessories first, so bag them separately. Old rubber and vinyl — Barbie limbs, figure capes — degrade and go sticky with age, so keep them cool and do not seal them airtight, which traps the plasticiser they give off.',
    watchOut: {
      title: 'Reproduction parts and resealed bubbles',
      body: 'The accessories get faked — a repro lightsaber, cape or blaster turns a complete figure into a partial one, and they are made to be indistinguishable in photographs. On carded pieces, watch for a resealed or replaced bubble, which is why expensive examples are bought graded (AFA and similar). Ask for close photos of the bubble edges and the accessory, and buy from specialists rather than general auction listings.',
    },
    valueDrivers:
      'Packaging above everything, then the specific variant — card back, hair colour, a running production change. Then completeness of accessories, then condition of the plastic. Scarcity here is usually accidental: a poor seller, a short final wave, a regional exclusive nobody exported. Which is exactly why the top of our catalogue is a European-exclusive Playmates figure at €252,528 rather than anything from the famous lines.',
    holyGrail: {
      title: 'Scratch (Playmates, European exclusive)',
      why: 'About €252,528 — a figure produced in tiny numbers for one market and largely cancelled. Nobody set out to make a valuable object; a distribution decision did it.',
    },
    entryLevel: {
      title: 'Loose figures from a line you remember',
      why: 'Half of what we track is under €42, and loose 1980s figures are genuinely cheap. Buy the line you had as a child, learn the accessories and card backs by handling them, and only then consider carded prices.',
    },
  },

  manga: {
    intro:
      'Manga collecting runs on first printings and out-of-print volumes rather than on rarity by design. The typical volume we track is €32, and the ceiling is a first-print Japanese Dragon Ball at €1,136.',
    whatItIs:
      'Japanese comics, published first as weekly or monthly chapters and then collected into paperback volumes called tankōbon. Nearly everything a collector cares about follows from that model. A first print of volume 1 was made before anyone knew the series would matter — Dragon Ball volume 1 from 1985, One Piece volume 1 from 1997 — so very few survive, while later printings of the same book are common and cheap. English editions are a separate market again, published years later by VIZ, Yen Press and others, where value comes from volumes that went out of print before a series finished. Condition expectations are unusual too: these are mass-market paperbacks with glued spines, so a truly flat, unread 1980s volume is rare in a way a hardback would not be.',
    glossary: [
      { term: 'Tankōbon', definition: 'The collected paperback volume, as opposed to the weekly magazine the chapters first appeared in.' },
      { term: 'First print', definition: 'The first printing of a volume, identified by the print date on the copyright page. This is the entire vintage market — later printings are common.' },
      { term: 'OOP', definition: 'Out of print. An English volume that stopped being reprinted — Vagabond vol 37 is about €862 for this reason alone.' },
      { term: 'Light novel', definition: 'Illustrated Japanese prose novels, often the source of a manga or anime. Collected alongside manga and priced the same way.' },
    ],
    care:
      'Store volumes upright and packed snugly enough that they cannot lean — a leaned paperback takes a permanent curve. Keep them out of sunlight, which fades the spine colour most people judge a set by, and out of damp, which warps a glued spine. Read gently or buy a second reading copy: a cracked spine on a first print is most of its value gone, and there is no restoration for it.',
    watchOut: {
      title: 'Later printings sold as firsts, and unlicensed imports',
      body: 'The difference between a €1,000 book and a €10 book is a line on the copyright page, and listings very often do not show it. Ask for a photo of that page rather than the cover. Separately, unlicensed printings of popular series circulate — off colours, thin paper, wrong trim size — sold as genuine imports to buyers who have never handled the real thing.',
    },
    valueDrivers:
      'First-print status of volume 1 for a series that became enormous, then condition, then whether an English edition is out of print. Complete runs sell for more than the sum of their volumes, and final volumes are disproportionately scarce because print runs shrink as a series ends — Slam Dunk vol 31 and Vagabond vol 37 are both in our top six for exactly that reason.',
    holyGrail: {
      title: 'Dragon Ball vol 1 — first print Japanese tankōbon (1985)',
      why: 'About €1,136. Printed before Dragon Ball was Dragon Ball, in ordinary numbers, on cheap paper, and read by children. Nothing about its production suggested anyone should keep it in good condition.',
    },
    entryLevel: {
      title: 'Current English volumes of a series you want to read',
      why: 'The median volume we track is €32 and new releases cost around €10. Read them, work out which series you love, and only chase first prints of the ones you would still want on the shelf in twenty years.',
    },
  },

  vinyl_records: {
    intro:
      'Records are collected for the pressing, not just the album. The typical record we track is €21, and the top is a limited soundtrack set at €1,400.',
    whatItIs:
      'The same album exists in many physical versions, and collectors care about which one is in the sleeve. A pressing is identified by the matrix number scratched into the run-out groove near the label, plus the label design and country of manufacture — which is how a first UK pressing is told from a 1980s reissue that looks identical in a photograph. Audiophile labels such as Mobile Fidelity licence albums and remaster them in limited runs, and those become collectable in their own right. Beyond that the market rewards the usual suspects: original pressings of albums that mattered, coloured or numbered variants, box sets, and film soundtracks pressed once for a small audience.',
    glossary: [
      { term: 'Matrix / runout', definition: 'Codes etched between the last groove and the label. They identify the exact pressing and are the only reliable way to tell one from another.' },
      { term: 'First pressing', definition: 'The original release run, before any repress. Usually the version collectors want — and usually the one a listing claims to have.' },
      { term: 'MFSL', definition: 'Mobile Fidelity Sound Lab, an audiophile reissue label. Their Nirvana Nevermind is about €643 in our catalogue.' },
      { term: 'Grading (VG+/NM)', definition: 'The Goldmine scale, applied separately to record and sleeve. A near-mint record in a beaten sleeve is priced as two separate facts.' },
    ],
    care:
      'Store records vertically and never stacked flat — weight warps them. Keep them out of heat, replace paper inner sleeves (which scuff) and keep the original inner behind the record in the jacket. Clean with a proper brush or wet cleaner, never a cloth, and handle by the edges. A warped or scratched record cannot be fixed; a dirty one usually can.',
    watchOut: {
      title: 'Reissues sold as originals',
      body: 'This is the whole game. A reissue can look identical to a first pressing and be worth a tenth as much, and plenty of sellers genuinely do not know the difference. Ask for a photo of the runout groove and the label, and check both against a discography before paying original-pressing prices. Be equally careful with "sealed" older records: resealing is easy and common.',
    },
    valueDrivers:
      'Pressing above all, then condition of record and sleeve separately, then scarcity of the specific variant — coloured, numbered or audiophile. Genre matters more than newcomers expect: original blues, jazz and early hip-hop pressings hold value strongly, and film scores pressed in small runs can outprice famous albums entirely. Our top record is a Lord of the Rings soundtrack set at €1,400.',
    holyGrail: {
      title: 'The Lord of the Rings: The Fellowship of the Ring — limited soundtrack set',
      why: 'About €1,400, and it is a soundtrack rather than a famous band — which is the lesson. In vinyl a small deliberate pressing for a devoted audience beats a legendary album that sold ten million copies.',
    },
    entryLevel: {
      title: 'Modern repressings of albums you want to hear',
      why: 'Half of what we track is under €21, and current repressings of classic albums cost about the price of a cinema ticket. They sound good, they cannot be passed off as something they are not, and they teach you to handle and clean records before you spend real money on an original.',
    },
  },

  nintendo_merch: {
    intro:
      'Nintendo collecting outside the games themselves is dominated by high-end statues and licensed collectibles. The typical item we track is €31, and the ceiling is a First 4 Figures Link statue at €3,506.',
    whatItIs:
      'Nintendo licenses very selectively, so the collectible market around it is smaller and more concentrated than the size of the franchises suggests. The serious end is statues, mostly from First 4 Figures — resin pieces of Link, Samus, Star Fox ships and the like, produced in numbered limited editions and sold largely by preorder direct from the maker. Around that sit amiibo (small NFC figures that also work in-game), plush, and a long tail of Japanese merchandise never sold in Europe or America. Because Nintendo rarely reissues anything and never discounts, an item that sells out tends to stay sold out — which is why so much of this category prices above its original retail.',
    glossary: [
      { term: 'First 4 Figures (F4F)', definition: 'The main licensed statue maker. Pieces are numbered, limited and usually preordered; the Twilight Princess Link statue is about €3,506 here.' },
      { term: 'Exclusive edition', definition: 'A version with extra parts or lighting sold only direct from the maker, in a smaller run than the standard edition.' },
      { term: 'amiibo', definition: 'Nintendo\'s small NFC figures. Most are cheap and common; a handful had tiny print runs and never returned.' },
      { term: 'JP exclusive', definition: 'Merchandise sold only in Japan, often through Nintendo\'s own stores. A large part of this category, and priced accordingly.' },
    ],
    care:
      'Resin statues are heavy, brittle and hand-painted: keep them out of direct sun (paint fades, resin yellows), away from heat, and never stack anything on the box. Keep the shipper carton and the numbered certificate — for a limited statue those are part of the item. For amiibo and boxed goods the card and window are the value, so treat them like carded figures rather than toys.',
    watchOut: {
      title: 'Recasts, and paying preorder prices for something you have not seen',
      body: 'Unlicensed recasts of popular statues circulate widely, with soft detail and rough paint, and they photograph well enough to pass in a listing. Buy from the maker or an authorised dealer and check the edition number against the certificate. The second trap is structural: this category runs on preorders a year ahead, which means money committed before reviews exist — and, on the secondary market, buyers paying over retail for pieces that are later restocked.',
    },
    valueDrivers:
      'Edition size and whether it was an exclusive version, then the character — Link and Samus outperform almost everything else. Then condition of piece and box together. Japanese exclusivity adds a premium simply because supply never reached most of the world. Note the shape of our catalogue: five of the six most expensive items here are statues, not games, plush or amiibo.',
    holyGrail: {
      title: 'First 4 Figures Link (Twilight Princess) statue',
      why: 'About €3,506 — a large numbered resin piece from a limited run that sold out on preorder and was never remade. Nintendo\'s refusal to reissue is what turns "sold out" into a permanent condition.',
    },
    entryLevel: {
      title: 'amiibo and current official merchandise',
      why: 'Half of what we track is under €31. amiibo cost about €15, are genuinely used in games, and a few quietly become scarce — the cheapest way into a category whose serious end starts in the hundreds.',
    },
  },

  vintage_cameras: {
    intro:
      'Vintage cameras are collected and used, often by the same person. The typical camera we track is €309 — the highest median of any non-luxury category here — and the top is a Leica at €33,569.',
    whatItIs:
      'Almost all of the money in this category is Leica, and it helps to know why. Leica made precise, hand-assembled 35mm rangefinders from the 1930s onward, in modest numbers, with lenses that are still used professionally today — so the same object is simultaneously a working tool and an antique. Rangefinder means you focus by aligning two images in a small bright window rather than through the lens, which is why these cameras feel nothing like a modern one. Bodies and lenses are collected separately and priced separately, and mount compatibility (M mount, screw mount) decides what fits what. Around Leica sits a wider hobby of Japanese and German makers — Nikon, Canon, Rollei, Hasselblad — where prices are a fraction of Leica\'s for cameras that take equally good photographs.',
    glossary: [
      { term: 'Rangefinder', definition: 'A focusing system using a superimposed second image in the viewfinder, rather than focusing through the lens. Leica\'s defining format.' },
      { term: 'Black paint', definition: 'A factory black finish on a chrome-era body, made in small numbers and prone to wearing through to brass — which collectors prize. A black paint M2 is about €18,116 here.' },
      { term: 'Glass / element', definition: 'The lens. Often worth more than the body, and priced by version — an early "steel rim" Summilux is €10,217 in our catalogue.' },
      { term: 'CLA', definition: 'Clean, lubricate, adjust — the standard service for a mechanical camera. A recent CLA meaningfully raises value.' },
    ],
    care:
      'Mechanical shutters seize when unused, so exercise the shutter at all speeds occasionally rather than leaving a camera in a drawer for years. Store with the shutter uncocked and away from damp: fungus growing inside a lens etches the coating permanently and is the single most common way a valuable lens is ruined. Keep silica gel in the bag, avoid attics and cellars, and never store leather cases against the body long-term — they hold moisture.',
    watchOut: {
      title: 'Fakes, Frankenstein bodies and hidden fungus',
      body: 'Leica is faked more than any other camera brand — repainted chrome bodies sold as factory black paint, engraved fantasy editions, and Soviet cameras rebuilt to look like 1930s Leicas. Ask for photos of the serial number and check it against published production records. Separately, always ask for a shot through the lens against a bright light: haze, separation and fungus are invisible in a normal listing photo and cost more to fix than most lenses are worth.',
    },
    valueDrivers:
      'Brand first, and it is mostly one brand — every one of the six most expensive items in our catalogue is a Leica. Then the specific variant: original black paint, an early lens version, a special edition. Then mechanical condition and service history, then cosmetic wear, which matters less here than elsewhere because honest brassing is desirable. Complete outfits with caps, hoods and boxes carry a premium.',
    holyGrail: {
      title: 'Leica MP Classic (black paint)',
      why: 'About €33,569 — a low-production, hand-finished film body made after digital had already taken over, for people who wanted the 1950s object built new. It shows what drives this category: not age, but deliberate scarcity of a mechanical thing.',
    },
    entryLevel: {
      title: 'A serviced Japanese SLR or fixed-lens rangefinder',
      why: 'Far below the €309 median. A CLA\'d Canon, Nikon or Olympus from the 1970s takes photographs indistinguishable from a Leica in ordinary use, costs a fraction, and teaches you what to check before you spend four figures on glass.',
    },
  },

  fragrances: {
    intro:
      'Fragrance collecting is driven by discontinuations and reformulations rather than by age. The typical bottle we track is €95, and the top is a niche house release at €1,576.',
    whatItIs:
      'The hobby divides into designer fragrances (fashion houses, sold everywhere) and niche houses — Frederic Malle, Amouage, Roja, Byredo — which produce in smaller quantities at much higher prices and are where nearly all collectable value sits. The concentration matters and is printed on the bottle: eau de toilette (EDT) is lighter and shorter-lived than eau de parfum (EDP), which in turn is lighter than extrait or pure parfum, and the same scent in a different concentration is a genuinely different product at a different price. The defining event in this market is reformulation: regulators periodically restrict ingredients (oakmoss and certain animalics especially), so houses quietly rework old formulas. Bottles from before a reformulation — "vintage" — can be worth many times the current version of the identical name.',
    glossary: [
      { term: 'EDT / EDP / Extrait', definition: 'Concentration, weakest to strongest. The same fragrance in extrait is a separate product from the EDT, not simply more of it.' },
      { term: 'Reformulation', definition: 'A change to the formula, usually forced by ingredient restrictions. The reason a sealed old bottle can be worth far more than a new one with the same label.' },
      { term: 'Batch code', definition: 'A short code stamped on the bottle or box identifying when it was made. How you tell a pre-reformulation bottle from a current one.' },
      { term: 'Decant', definition: 'A small amount of a fragrance transferred into a sample vial. How most people try expensive or discontinued scents without buying a full bottle.' },
    ],
    care:
      'Fragrance degrades with light, heat and air — the three things a bathroom shelf provides. Store bottles upright in their boxes, somewhere cool and dark, and do not display them in sunlight however good they look. A partly used bottle ages faster because of the air inside, so a sealed bottle is worth substantially more than a half-full one of the same age. Never decant into a container that is not proper glass with a tight seal.',
    watchOut: {
      title: 'Counterfeits and "vintage" that is just old stock',
      body: 'Fakes are widespread and increasingly good, down to the box and cellophane — buy sealed from established retailers or trusted community sellers, and check the batch code against the house\'s own records. The other trap is language: "vintage" should mean pre-reformulation, but is used loosely for anything that has sat in a warehouse. Ask for a photo of the batch code rather than accepting the word.',
    },
    valueDrivers:
      'Discontinuation first, then pre-reformulation status, then the house — niche names dominate the top of our catalogue, with Frederic Malle\'s The Night at €1,576 in EDT and €953 in parfum. Then concentration, then fill level and seal. Packaging matters less than in most categories, but an unopened bottle in its box is the benchmark against which everything else is discounted.',
    holyGrail: {
      title: 'Frederic Malle — The Night (EDT 100ml)',
      why: 'About €1,576. A limited niche release built on expensive oud, produced in small quantities and priced accordingly from the start — this is a category where the grail was expensive when new rather than becoming so.',
    },
    entryLevel: {
      title: 'Decants and samples',
      why: 'Half of what we track is under €95, but you should not start with a bottle at all. A few euros gets you a 2ml decant of almost anything, including discontinued scents. Wear it for a full day before buying 100ml of it — fragrance changes over hours, and a shop sniff tells you almost nothing.',
    },
  },

  diecast: {
    intro:
      'Diecast model cars run from pocket-money castings to hand-built museum pieces. The typical model we track is €44, and the top is a 1:50 crane at €1,554.',
    whatItIs:
      'Scale metal models, and the scale is the first thing in every listing: 1:18 is roughly 25cm and the main collector size, 1:43 is the traditional European display scale, 1:64 is Hot Wheels size. Above the mass market sits a tier of manufacturers — CMC, BBR, MR Collection, AUTOart — building limited runs with opening panels, wired engines, photo-etched details and hand-laid paint, which is why a single 1:18 car reaches four figures. A separate and surprisingly strong branch is construction and commercial vehicles: cranes, excavators and trucks, often bought by people in the industry, where a detailed 1:50 crane can outprice any car in the catalogue. Sealed box and unbuilt condition matter, but unlike toys these are display models — they were bought by adults and mostly kept well.',
    glossary: [
      { term: '1:18 / 1:43 / 1:64', definition: 'Scale. 1:18 is the main collector size at about 25cm; 1:43 is the classic display scale; 1:64 is Hot Wheels size.' },
      { term: 'Sealed / mint boxed', definition: 'Unopened, with the outer sleeve and inner packaging. The benchmark condition for anything limited.' },
      { term: 'Limited edition number', definition: 'Most premium models state a run size and a certificate. Both are part of the item\'s value.' },
      { term: 'Resin vs diecast', definition: 'Premium models are increasingly cast resin rather than metal — lighter, finer detail, but usually no opening parts.' },
    ],
    care:
      'Dust and sunlight are the two enemies: UV fades paint and yellows clear plastic windows permanently, and dust is abrasive once you wipe it. Keep models in acrylic cases or their boxes, and handle with clean hands or cotton gloves, because fingerprints etch some paint finishes over time. Rubber tyres on older models harden and can crack; keep the wheels off pressure by storing on a shelf rather than stacked in boxes.',
    watchOut: {
      title: 'Reboxed commons and missing certificates',
      body: 'Limited premium models are sold on their numbering, so a model without its certificate and box is worth much less — and boxes are routinely swapped to dress a common version as a limited one. Check that the number on the certificate matches the base plate. Also be careful with "rare colourway" claims: many manufacturers issue the same casting in several colours, and only some were genuinely limited.',
    },
    valueDrivers:
      'Manufacturer and build quality first — CMC, BBR and MR occupy the top of our catalogue, and the gap between them and mass-market brands is enormous. Then edition size, then subject: Ferrari, Porsche and famous racing liveries hold value best among cars, while heavy machinery models sell to a separate and dedicated audience. Sealed condition with certificate is the benchmark; opened but mint is a modest discount, damaged detail parts a heavy one.',
    holyGrail: {
      title: 'Liebherr LR 1600/2 Crawler Crane (NZG, 1:50)',
      why: 'About €1,554, and it is a crane rather than a supercar — which is the useful surprise in this category. Detailed construction models are bought by people who work with the real machines, and that audience is small, knowledgeable and willing to pay.',
    },
    entryLevel: {
      title: 'A 1:18 model of a car you love, from a mainstream maker',
      why: 'Half of what we track is under €44. A mainstream 1:18 gives you real presence on a shelf for the price of a takeaway, and handling one teaches you what the four-figure models are actually offering before you buy one.',
    },
  },

  loungefly: {
    intro:
      'Loungefly makes licensed mini backpacks and bags, sold as fashion and collected as merchandise. The typical bag we track is €62, and the top is a retired Disney design at €615.',
    whatItIs:
      'A single brand rather than a category of object: faux-leather mini backpacks, crossbody bags and wallets, printed or appliquéd with Disney, Pokémon, Sanrio and similar licences. They are produced in waves and retired rather than reissued, and a substantial part of the range is exclusive — to one retailer, one park, one convention, or in the case of Club 33 to a private Disneyland membership most people cannot buy into at all. That structure is what makes them collectable: the object is a wearable bag with a genuinely finite production run, so scarcity arrives quickly and permanently once a design sells through. Condition expectations follow from that too — these are used bags, so unused ones with tags are the exception rather than the norm.',
    glossary: [
      { term: 'Exclusive', definition: 'Sold only through one retailer, park or event. The single biggest driver of value here — the Club 33 sequin backpack is about €376.' },
      { term: 'Sequin / appliqué', definition: 'Finish types. Sequinned and heavily appliquéd designs are produced in smaller numbers and hold value better than flat prints.' },
      { term: 'NWT', definition: 'New with tags — unused with the original hangtag attached. The benchmark condition.' },
      { term: 'Retired', definition: 'No longer produced. Loungefly reissues very rarely, so retirement is effectively permanent.' },
    ],
    care:
      'The faux leather is the fragile part: it cracks in dry heat and peels if it stays damp, so keep bags out of hot cars and never machine wash one. Stuff them lightly when stored so the front panel does not crease inward, and keep sequinned designs in a dust bag, since loose sequins cannot be replaced convincingly. Keep the hangtag if you have it — for an unused bag it is part of the value.',
    watchOut: {
      title: 'Counterfeits and stretched "exclusive" claims',
      body: 'Fakes are common on general marketplaces, and the tells are printing quality, stitching around the zips, and the metal hardware, which on genuine bags is weighty and evenly finished. Buy from the licensed retailers or specialists where you can. Second, be sceptical of the word exclusive: park and Club 33 exclusives are real and command real premiums, but the term is applied loosely to bags that were simply sold in one chain.',
    },
    valueDrivers:
      'Exclusivity and retirement first, then the licence — Disney park designs dominate the top of our catalogue, with the Tarzan jungle scene backpack at €615 and the Snow White Evil Queen sequin bag at €441. Then finish, with sequins and scene designs above flat prints. Then condition, where new-with-tags is the benchmark and visible wear discounts heavily, because these are bags people actually carry.',
    holyGrail: {
      title: 'Tarzan Jungle Scene mini backpack',
      why: 'About €615 — a retired design for a film with a small but devoted following, produced once in a modest run. It illustrates the rule here: the biggest licence does not win, the smallest production does.',
    },
    entryLevel: {
      title: 'A current design for something you actually like',
      why: 'Half of what we track is under €62, and current releases sit at retail. Buy one to carry. It is a functional bag first, and the ones that appreciate do so because they retired, which nobody can predict at the point of sale.',
    },
  },

  bluray_steelbook: {
    intro:
      'Steelbooks are metal cases for films and series, produced in limited runs by region. The typical one we track is €31, and the top is a 4K box set at €878.',
    whatItIs:
      'A steelbook is the same disc in a metal case with original artwork, released instead of or alongside the normal plastic edition. What makes them collectable is that they are regional and finite: a design released in Germany or Japan may never be sold elsewhere, runs are numbered or capped, and boutique labels — HDZeta, Kimchi, Manta Lab in Asia; Arrow and Criterion in the West — produce elaborate editions with slipcases, lenticular covers and booklets. Region coding still matters for the discs inside (Blu-ray regions A/B/C), though 4K UHD discs are region-free, which is why 4K steelbooks travel between markets more easily than older Blu-rays. "One click", "full slip" and "lenticular" describe which packaging tier of the same release you are buying.',
    glossary: [
      { term: 'One click / full slip / lenticular', definition: 'Packaging tiers of a boutique release, cheapest to most elaborate. A "one click" Interstellar from HDZeta is about €540 here.' },
      { term: 'Region code', definition: 'Blu-ray discs are locked to region A, B or C. 4K UHD discs are region-free, which is why 4K editions import cleanly.' },
      { term: 'Boutique label', definition: 'A specialist publisher producing limited numbered editions — HDZeta, Manta Lab, Arrow, Criterion.' },
      { term: 'OOP', definition: 'Out of print. Steelbooks are rarely reprinted, so a sold-out edition stays sold out.' },
    ],
    care:
      'The case is the collectable, and metal dents. Store steelbooks upright and snug, never stacked flat under weight, and keep them out of damp because the printing lifts and the edges can spot with rust. Slipcases crush easily, so shelve them with support at both ends. If you actually watch the discs, take care with the inner hub — repeated removal chips the plastic teeth on some editions and there is no replacement.',
    watchOut: {
      title: 'Region locks and reprints of "limited" editions',
      body: 'Buying an imported Blu-ray steelbook that will not play on your machine is the classic beginner mistake — check the region code before you pay, or stick to 4K UHD, which is region-free. Also treat "limited" carefully: mainstream retailer steelbooks are often produced in large numbers and reissued, while boutique editions with stated numbering are the genuinely finite ones.',
    },
    valueDrivers:
      'Whether the edition sold out and stayed out of print, then packaging tier — lenticular and full-slip editions above one-click, which is above plain. Then the film, where cult and prestige titles outperform blockbusters. Complete series box sets do unusually well, with The Dark Knight Trilogy 4K set at €878 and Game of Thrones at €351. Condition of the metal and the slip decides the rest.',
    holyGrail: {
      title: 'The Dark Knight Trilogy 4K box set (steelbook)',
      why: 'About €878. A complete-trilogy set in a format people actually want to keep, produced once — it is the pattern in this category: box sets and boutique numbered editions above single-film releases, however famous the film.',
    },
    entryLevel: {
      title: 'A retailer steelbook of a film you rewatch',
      why: 'Half of what we track is under €31, and standard retailer steelbooks are often the same price as the plastic edition. Start there, learn which labels and tiers you care about, and only then chase numbered boutique releases.',
    },
  },

  designer_toys: {
    intro:
      'Designer toys are art objects in toy form — produced in limited runs, often as collaborations between a toy maker and an artist or fashion house. The typical piece we track is €100, and the top is €65,703.',
    whatItIs:
      'The category is dominated by one product: the BE@RBRICK, a blocky bear figure made by the Japanese company Medicom since 2001. It is deliberately a blank canvas — the same shape every time, decorated by a different artist, brand or film licence, which is what lets a bear become a Chanel object or a KAWS sculpture. Sizes are given as percentages of the original 7cm figure: 100% is keychain-sized, 400% about 28cm, and 1000% roughly 70cm and the size that reaches five figures. Around Medicom sits a wider art-toy world — KAWS, Daniel Arsham, Coarse — where pieces are released as numbered drops, sell out in minutes, and trade immediately above retail. The important cultural point is that these are bought as contemporary art by people who also buy paintings, which is why the ceiling is so far above the rest of the toy market.',
    glossary: [
      { term: 'BE@RBRICK', definition: 'Medicom\'s bear-shaped figure, made since 2001 and decorated by artists and brands. The backbone of the entire category.' },
      { term: '100% / 400% / 1000%', definition: 'Size, as a multiple of the original 7cm figure. 1000% is about 70cm and where the money is — the Chanel 1000% is €65,703 here.' },
      { term: 'Drop', definition: 'A timed release, usually online, in a fixed quantity. Most designer toys are sold this way rather than stocked.' },
      { term: 'Collaboration', definition: 'A piece designed with an outside artist or house. Almost every four- and five-figure item in this category is one.' },
    ],
    care:
      'These are painted plastic and resin display objects: keep them out of direct sun, which fades and yellows, and off surfaces that get hot. Large sizes are heavy and top-light, so stand them where they cannot topple — a 1000% falling is usually a chipped paint edge at best. Keep the box and any authentication card; for numbered art pieces the packaging is part of the object, and buyers ask for it.',
    watchOut: {
      title: 'Fakes are an industry here',
      body: 'Counterfeit BE@RBRICKs and KAWS figures are produced at scale, and the good ones copy the box, the sticker and the finish. Check the Medicom logo moulding on the foot, the paint edges, and the weight, and buy from authorised retailers or established resellers. Be especially careful at the 1000% size, where a single sale is worth enough to justify a very convincing fake.',
    },
    valueDrivers:
      'Collaborator first — a Chanel or KAWS bear is a different market from a film tie-in, and our top two items are both Chanel 1000%s at €65,703 and €44,084. Then size, where 1000% commands a large multiple over 400%. Then edition size and whether it sold out at retail. Condition matters, but as with art the object is rarely handled: box, certificate and unfaded paint are what people check.',
    holyGrail: {
      title: 'BE@RBRICK 1000% Chanel (black/white)',
      why: 'About €65,703 — a fashion-house collaboration at the largest size, made in tiny numbers and never intended as a toy. It is the clearest example of the category\'s logic: the value comes from the name painted on the bear, not from the bear.',
    },
    entryLevel: {
      title: 'A 100% or 400% BE@RBRICK series figure',
      why: 'Half of what we track is under €100. Series bears come in sealed boxes at modest prices, give you the exact object at a smaller size, and are the cheapest way to learn what genuine paint, moulding and packaging look like before you spend real money.',
    },
  },

  blind_box: {
    intro:
      'Blind boxes are sealed figures you buy without knowing which one is inside. The typical box we track is €33 — but the rare pulls behind them reach €6,628.',
    whatItIs:
      'A blind box is a sealed package containing one figure from a stated series, usually of twelve or so designs, with published or implied odds. The point is the gamble: you buy the series, not the figure. Every line includes at least one "secret" — a chase figure at long odds, sometimes one in a hundred or more — and that figure carries most of the series\' resale value. Chinese and Japanese makers dominate: Pop Mart, 52TOYS, Medicom and a long list of artist collaborations. A "full case" contains a complete assortment and is bought by people who would rather guarantee the set than gamble box by box; a "sealed set" of an old series is worth substantially more than the loose figures it contains.',
    glossary: [
      { term: 'Secret / chase', definition: 'The rare figure in a series, pulled at long odds. A Panda Roll secret gold panda is about €6,628 in our catalogue.' },
      { term: 'Full case', definition: 'A sealed box containing a complete assortment, so you get every design without gambling.' },
      { term: 'Weighing / feeling', definition: 'Trying to identify the contents before buying, by weight or shape. Frowned upon, widely done, and the reason sealed cases from a shop are safer than loose boxes from a bin.' },
      { term: 'Pop Mart / 52TOYS', definition: 'The dominant makers. Their series drive most of the category\'s volume and nearly all of its resale.' },
    ],
    care:
      'The figures are small, painted vinyl and easy to scuff, so keep them off surfaces where they get knocked, and out of sunlight, which fades pastel finishes fast. Keep the box, the inner bag and the little card that comes with the figure — a complete boxed example is worth noticeably more than a loose one, and the card is the first thing lost. If you are keeping a series sealed as an investment, keep it somewhere dry: cardboard warps and that shows.',
    watchOut: {
      title: 'Pre-opened boxes and fake secrets',
      body: 'The specific fraud here is a box that has been opened, checked and resealed with the common figure put back — buy sealed cases from proper retailers rather than single boxes from open bins. Counterfeit secret figures also circulate, since the chase is where the money is; compare paint detail and the base stamp against known genuine photos before paying a secret-figure price.',
    },
    valueDrivers:
      'Whether it is a secret figure, first and foremost — that single pull is worth many times the rest of its series combined. Then the artist or collaboration: KAWS-related Medicom sets sit at €2,400–€3,360 here. Then whether a series is retired, then condition and completeness with box and card. Sealed cases of retired series hold value better than any individual common figure.',
    holyGrail: {
      title: '52TOYS Panda Roll — Secret Gold Panda',
      why: 'About €6,628. A secret figure at extremely long odds from a mass-market series that cost a few euros a box — the entire category\'s economics in one object.',
    },
    entryLevel: {
      title: 'A single box from a current series you like the look of',
      why: 'Half of what we track is under €33, and one box is a genuinely fun purchase at pocket-money prices. Buy for the design you hope to get rather than the secret you probably will not — the odds are published and they are not in your favour.',
    },
  },

  ghibli: {
    intro:
      'Studio Ghibli collecting is unusual: the valuable objects are not merchandise at all, but original hand-painted production art. The typical item we track is €58, and the top is a Totoro cel at €10,792.',
    whatItIs:
      'Ghibli made its films by hand, on celluloid, into the 2000s — far later than most studios. Every frame was drawn, inked and painted, so a finished film left behind tens of thousands of unique physical objects. A "cel" is one of those painted acetate sheets, sometimes sold with the hand-painted background it was photographed against, which is why a cel with background is worth several times one without. The studio also released relatively little licensed merchandise for decades and kept tight control of it, so official plush, figures and the Museum-exclusive items sit in a smaller, cleaner market than most anime franchises. Between those two poles there is very little — this is a category of cheap official goods and expensive one-of-one art, with not much in the middle.',
    glossary: [
      { term: 'Cel', definition: 'A hand-painted celluloid sheet photographed as one frame of the film. Unique by definition — no two are identical.' },
      { term: 'Background (BG)', definition: 'The painted scenery a cel was shot against. A cel sold WITH its matching background is the premium configuration — the Totoro hole cel with background is €10,792 here.' },
      { term: 'Douga / genga', definition: 'The pencil drawings behind a cel — douga is the clean traced drawing, genga the animator\'s original key drawing.' },
      { term: 'Museum exclusive', definition: 'Merchandise sold only at the Ghibli Museum in Mitaka, never through normal retail.' },
    ],
    care:
      'Cels are the fragile thing: acetate yellows, warps and eventually becomes brittle, and the paint can lift from the back if it is flexed. Keep them flat, framed with UV-filtering glass, away from heat and humidity, and never stack them directly on each other — use interleaving. Do not attempt to clean a cel; the paint is water-soluble and a wipe can take the character off the sheet. For merchandise, the usual rules apply: boxes out of sunlight, plush out of damp.',
    watchOut: {
      title: 'Reproduction cels and unverifiable provenance',
      body: 'Printed reproductions are sold as originals constantly, and a photograph will not tell you the difference — a genuine cel has visible paint thickness on the reverse and hand-inked lines, a repro does not. Buy from dealers who state provenance and offer returns, and be sceptical of "studio stamp" claims without documentation. Separately, a great deal of unlicensed Ghibli merchandise exists, especially plush and figures sold at low prices.',
    },
    valueDrivers:
      'For art: which character and which moment, then whether the matching background is included, then condition of the acetate. Totoro and the most famous scenes command the premium — our top four items are all Totoro, Kiki or Porco Rosso key moments. For merchandise: Museum exclusivity, age, and whether it was ever sold outside Japan. Everything else in the category is priced modestly, and that is normal rather than a gap.',
    holyGrail: {
      title: 'Mei discovering the Totoro hole — animation cel with background',
      why: 'About €10,792. A single frame from one of the most recognisable scenes in animation, hand-painted, with its original background — a genuinely unique object from a film that was made before anyone treated production art as an asset.',
    },
    entryLevel: {
      title: 'Official merchandise, or a douga rather than a cel',
      why: 'Half of what we track is under €58. Official plush and figures are affordable, and if you want something from the production itself, a douga — a pencil drawing rather than a painted cel — is a fraction of the price and just as genuinely from the film.',
    },
  },

  oop_board_games: {
    intro:
      'Out-of-print board games are collected because printing stopped, not because they are old. The typical game we track is €41, and the top is a small-press design at €15,129.',
    whatItIs:
      'Board games are printed in limited runs by publishers who often never reprint — so a game that reviewed well and sold out can become permanently unavailable while the community that wants it keeps growing. Three sources of scarcity dominate. Small European publishers such as Splotter Spellen print a few thousand copies of complex games and move on. Kickstarter editions bundle exclusive content that never reaches retail, so the crowdfunded version is a different object from the shop one. And licensed games — Games Workshop\'s especially — go out of print when the licence lapses, permanently. Condition language is borrowed from other hobbies but with a twist specific to board games: punched or unpunched cardboard, since components come on sprues that you separate by hand the first time you play.',
    glossary: [
      { term: 'OOP', definition: 'Out of print, with no reprint announced. The single reason most of this category is expensive.' },
      { term: 'Unpunched', definition: 'The cardboard components are still attached to their sheets — the game has never been played. Commands a real premium.' },
      { term: 'Kickstarter edition', definition: 'A crowdfunded version with exclusive components that never reached shops. Usually worth more than the retail edition of the same game.' },
      { term: 'Sleeved', definition: 'Cards in protective sleeves. A well-sleeved used copy can be worth more than an unsleeved one in similar condition.' },
    ],
    care:
      'Store games flat, not upright — boxes are cardboard and the weight of components warps a box stood on its edge, which is the most common damage in this category. Keep them out of damp, since board warping is permanent and obvious. Bag components by type rather than tipping everything into the box, and if a game has a lot of cards, sleeve them: the cards are what wear first and a full replacement set rarely exists.',
    watchOut: {
      title: 'Missing components and "complete" that is not',
      body: 'A board game is worth a fraction of its value with one component missing, and there is no easy replacement for an out-of-print title. Ask for confirmation against a published component list rather than accepting the word complete, and be careful with second-hand copies of games with dozens of small pieces. Kickstarter exclusives are also routinely sold as part of "complete" retail copies when they are separate items.',
    },
    valueDrivers:
      'Whether it is out of print and how unlikely a reprint is, then edition — Kickstarter with exclusives over retail. Then completeness and whether the cardboard is punched. Then the game\'s standing among players, which for this category is driven by a small number of very influential reviewers. Note the shape: our top item is €15,129 and the next is €439, so this is a category with one extraordinary outlier and a long, affordable tail.',
    holyGrail: {
      title: 'Bus (Splotter Spellen)',
      why: 'About €15,129. A dense economic game printed in tiny numbers by a two-person Dutch publisher in the late 1990s, never widely reprinted, and steadily more admired ever since — scarcity from a publisher\'s scale rather than from age or licence.',
    },
    entryLevel: {
      title: 'A recently out-of-print game you actually want to play',
      why: 'Half of what we track is under €41. Games that went out of print in the last few years are affordable, playable and the most likely to appreciate quietly. Buy one you will put on the table — a sealed copy you never open is worth more, and worth nothing to you.',
    },
  },

  marvel_legends: {
    intro:
      'Marvel Legends is Hasbro\'s 6-inch action figure line, and the collectable end of it is dominated by giant crowdfunded pieces. The typical figure we track is €22, and the top is €2,248.',
    whatItIs:
      'A long-running line of highly articulated 6-inch figures covering essentially the whole Marvel roster, sold at ordinary toy prices and released in waves. Two mechanics make it collectable. Waves are built around a "Build-A-Figure": each figure in the wave includes one part of a larger character, so collecting the whole wave assembles an extra figure — and a loose BAF part missing from a resale is a real problem. Separately, HasLab is Hasbro\'s crowdfunding programme: enormous pieces funded by preorder, produced once in the exact quantity backed and never reissued. That is where the money is, and why our most expensive item in this category is a Star Wars sail barge rather than a Marvel character at all.',
    glossary: [
      { term: 'BAF (Build-A-Figure)', definition: 'A larger figure split across a wave, one part per box. Missing parts are the most common problem with second-hand figures.' },
      { term: 'HasLab', definition: 'Hasbro\'s crowdfunded line — huge items made once, in the quantity backed. Jabba\'s Sail Barge is €2,248 here; Galactus €613.' },
      { term: 'Wave', definition: 'A batch of figures released together, usually sharing a BAF. Waves sell out unevenly, which is what makes single figures scarce.' },
      { term: 'Loose vs carded', definition: 'Out of packaging versus sealed. In this line, loose is normal and carded carries a modest premium — nothing like vintage toys.' },
    ],
    care:
      'These are display figures with a lot of joints: avoid extreme poses for long periods, and be careful with cold plastic, which snaps rather than flexes — warm a stiff joint before forcing it. Keep them out of sunlight, which yellows lighter plastics permanently. Bag and label BAF parts and accessories separately the moment you open a wave; the value of a complete set depends entirely on parts that are easy to lose.',
    watchOut: {
      title: 'Incomplete Build-A-Figures and HasLab preorder risk',
      body: 'Buying a wave second-hand usually means chasing missing BAF parts at silly prices, so confirm exactly which parts and accessories are included before paying. On the HasLab side, the risk is structural: you commit money a year ahead for something that only exists if the campaign funds, and cancellations do happen — never back one at a price you would not pay to own it outright.',
    },
    valueDrivers:
      'HasLab status above everything: the four most expensive items we track are all HasLab pieces, at €2,248 down to €420. Then complete BAF sets, then individual figures that shipped in short waves or were retailer exclusives. Character popularity matters less than availability — a well-liked character released in a large wave stays cheap indefinitely.',
    holyGrail: {
      title: "Jabba's Sail Barge (HasLab)",
      why: 'About €2,248. A metre-long vehicle produced once, only in the number of people who backed it, and never made again. Worth noting it is Star Wars rather than Marvel: the money in this line follows the crowdfunding mechanic, not the licence.',
    },
    entryLevel: {
      title: 'Loose figures of characters you like',
      why: 'Half of what we track is under €22, and loose Marvel Legends are among the cheapest well-made action figures you can buy. Start loose, decide whether you care about complete waves, and only then take on the BAF chase.',
    },
  },

  scale_models: {
    intro:
      'Scale models are kits you build and paint yourself — aircraft, ships, armour and sci-fi. The typical kit we track is €36, and the top is a large-scale bomber at €634.',
    whatItIs:
      'Unlike Gunpla, most scale kits need glue, filler and paint: parts come in plain grey or coloured plastic on runners, and everything about the finished look is down to you. Scale is written as a ratio and it is the first thing in any listing — 1/72 and 1/48 dominate aircraft, 1/35 armour, 1/350 and 1/700 ships. The hobby is old, deeply documented and full of long-discontinued moulds, which is where collecting comes in: a kit from a mould that has not been produced for decades, still sealed with its decals intact, is the scarce object. Aftermarket is a whole industry alongside it — resin detail sets, photo-etched brass, replacement decals — bought to improve a kit that may itself be cheap.',
    glossary: [
      { term: '1/72, 1/48, 1/35', definition: 'Scale. Smaller number after the slash means a bigger model — 1/32 is large, 1/700 is tiny.' },
      { term: 'Sprue / runner', definition: 'The plastic frame the parts arrive attached to. "Sealed sprues" in a listing means the bags were never opened.' },
      { term: 'Photo-etch (PE)', definition: 'Thin brass detail parts, usually aftermarket, for things plastic cannot render — grilles, seatbelts, railings.' },
      { term: 'Decals', definition: 'The waterslide markings. They yellow and go brittle with age, which is why an old sealed kit can still be a disappointment.' },
    ],
    care:
      'Store kits flat and dry — a crushed box is a real value loss and damp destroys decals long before it touches the plastic. Old decals are the weak point of any vintage kit: keep them out of heat, and expect to buy replacements for anything from the 1970s or 80s regardless of how the box looks. Built models need a display case; dust on a matt-painted model cannot be wiped off without marking the finish.',
    watchOut: {
      title: 'A sealed vintage box is not a complete kit',
      body: 'The classic mistake is paying vintage prices for a sealed kit whose decals have yellowed to unusable and whose plastic has gone brittle. Ask for photos of the sprues and the decal sheet where the seller can provide them, and price an old kit as plastic plus a replacement decal set. Also check for reboxes: manufacturers licence each other\'s moulds constantly, so the same kit appears under several brands at very different prices.',
    },
    valueDrivers:
      'Whether the mould is out of production, then scale and subject — large-scale aircraft and famous ships command the most, with the 1/32 Lancaster at €634 in our catalogue. Then completeness and decal condition. Bandai\'s licensed Star Wars kits sit oddly high for their size because they are only sold in Japan. Built models sell for much less than kits unless the builder is well known, since the buyer is paying for someone else\'s work.',
    holyGrail: {
      title: 'Lancaster B.III "Dambusters" (1/32)',
      why: 'About €634 — an enormous kit of a famous aircraft, produced in limited quantities because very few people have the shelf space for a metre-wide bomber. Physical size is a genuine scarcity driver in this hobby.',
    },
    entryLevel: {
      title: 'A current 1/72 aircraft kit and a few paints',
      why: 'Half of what we track is under €36 and current kits cost far less. Build something small and modern before buying anything vintage — you will learn what a good moulding looks like, and you cannot ruin anything scarce while you learn.',
    },
  },

  theme_park: {
    intro:
      'Theme park collecting is about objects you could only get by physically being somewhere. The typical item we track is €32, and the top is a Club 33 commemorative at €698.',
    whatItIs:
      'Merchandise sold inside parks, and — more interestingly — objects from the parks themselves. Disney dominates, but Europa-Park, Universal and Tokyo DisneySea all have their own followings. Three kinds of thing carry value. Park-exclusive merchandise, sold in one resort and often for one season only. Event and anniversary pieces made in stated quantities. And genuine ride ephemera: props, signage, ride vehicles and decor sold off when an attraction closes or is refurbished, which is the closest this hobby gets to production art. Club 33 sits above all of it — a private membership club inside Disneyland whose merchandise is not sold to the public at all, which is why it prices the way it does.',
    glossary: [
      { term: 'Park exclusive', definition: 'Sold only inside one resort. The most common source of scarcity here — no online store, no reissue.' },
      { term: 'Club 33', definition: 'Disney\'s private membership club. Its merchandise cannot be bought by the public, so it commands a large premium — the 50th anniversary piece is €698 here.' },
      { term: 'Ride ephemera', definition: 'Props, signage and decor from an attraction, usually released when a ride closes or is refurbished.' },
      { term: 'Opening day', definition: 'Merchandise made for a ride or park\'s debut, in small quantities, and never reissued.' },
    ],
    care:
      'Most of this is printed, painted or fabric merchandise, so the enemies are sunlight and damp: keep pins on boards, textiles out of light, and paper items (maps, opening-day guides) flat between acid-free sheets. Ride ephemera is often old and was never made to last — treat it as an antique rather than a toy, and do not clean or repaint anything, since originality is the entire value.',
    watchOut: {
      title: 'Provenance is everything, and it is rarely documented',
      body: '"Ride-used" and "prop" claims are made constantly and proved rarely. Genuine ride ephemera usually comes with an auction history or a Disney sale record; anything without documentation should be priced as decor, not as an artefact. For Club 33 items, the market is small enough that fakes exist and are worth the effort — buy from established specialists, not from general marketplaces.',
    },
    valueDrivers:
      'Exclusivity and where it was sold, then whether it commemorated something specific — an anniversary, an opening, a closure. Then age, then condition. Note how the pattern shows in our data: the top items are a Club 33 anniversary piece, a Tokyo DisneySea ride miniature and a Main Street confectionery item, all of which required being in a particular building on a particular day.',
    holyGrail: {
      title: 'Club 33 50th Anniversary commemorative',
      why: 'About €698 — from a private club with a waiting list measured in years, made for members only. This category\'s ceiling is not about production numbers but about access: some objects were never purchasable by the public at any price.',
    },
    entryLevel: {
      title: 'Pins and current park merchandise, bought on a visit',
      why: 'Half of what we track is under €32. Pins in particular are cheap, tradable in the parks, and the item most tied to actually being there — which is what this category is really about.',
    },
  },

  bandai_premium: {
    intro:
      'Bandai Premium is Bandai\'s web-exclusive line — figures and collectibles sold only online, in one production window, and never restocked. The typical item we track is €118, one of the highest medians in the app.',
    whatItIs:
      'Not a category of object but a channel. Bandai sells its mainstream figures through shops, and reserves a large parallel range for its own web store: Soul of Chogokin die-cast robots, S.H.Figuarts characters too niche for retail, Ichiban Kuji prize figures, and endless variants of characters that already exist. The mechanic that matters is the ordering window: an item is announced, orders are taken for a few weeks, the quantity ordered is what gets made, and then it is gone permanently. That produces scarcity with no relationship to demand — an unpopular character ordered by few people becomes far harder to find than a popular one everyone ordered. Most items ship to Japan only, so Western buyers use proxy services, which adds cost and time to everything.',
    glossary: [
      { term: 'P-Bandai', definition: 'The common shorthand for Bandai Premium web exclusives. One order window, no restock.' },
      { term: 'Soul of Chogokin (SOC)', definition: 'Bandai\'s premium die-cast robot line. Heavy, expensive and the top of our catalogue here — the GX-85 pieces are €709–€979.' },
      { term: 'Ichiban Kuji', definition: 'A Japanese prize-lottery line sold in shops: every ticket wins a figure, with a top prize like the €1,005 Madara Perfect Susanoo.' },
      { term: 'Proxy / forwarder', definition: 'A service that buys Japan-only items on your behalf and reships them. Standard practice for this category.' },
    ],
    care:
      'Die-cast lines are heavy and their paint chips at the joints, so pose them gently and support the weight when you move them. Keep boxes — for a web exclusive the box is part of the item and the only proof of what it is. Watch for zinc pest on older die-cast: pieces made from poor alloy can swell and crack from the inside decades later, and nothing can be done once it starts, so store in stable, dry conditions.',
    watchOut: {
      title: 'Bootlegs of sold-out exclusives, and proxy costs',
      body: 'A sold-out P-Bandai release is exactly what bootleggers target, and copies of popular Figuarts are widespread — check the joint tolerances, the paint edges and the box print, and buy from established importers. The other trap is arithmetic: an item at a fair Japanese price can double after proxy fees, domestic shipping, international shipping and customs, and none of that is recoverable when you sell.',
    },
    valueDrivers:
      'How small the order window turned out to be, which is unknowable in advance and is why this category rewards ordering on release. Then line — Soul of Chogokin and Ichiban Kuji top prizes hold value best. Then whether the character had a moment after the window closed, since Bandai cannot respond to it. Boxed condition matters; loose exclusives lose a large share of their value.',
    holyGrail: {
      title: 'Ichiban Kuji Madara Perfect Susanoo (Last One prize)',
      why: 'About €1,005 — a top-tier lottery prize that could not be bought directly at all, only won, and only in Japan. It is the purest expression of this channel\'s logic: availability decided by a process, not by price.',
    },
    entryLevel: {
      title: 'A standard-retail S.H.Figuarts of a character you like',
      why: 'Half of what we track is under €118, and the mainstream Figuarts line is sold normally in shops worldwide at a fraction of exclusive prices. Buy one, see whether the build quality is worth it to you, and only then take on proxy fees and order windows.',
    },
  },

  retro_handhelds: {
    intro:
      'Handheld consoles are collected for the hardware itself — Game Boys, Game Gears, oddities and limited re-releases. The typical unit we track is €48, and the top is a Tamagotchi at €1,973.',
    whatItIs:
      'Portable games hardware from the late 1980s onward, plus the small ecosystem of virtual pets and obscure competitors that grew up alongside it. The market has three parts. Mainstream classics — Game Boy, Game Boy Advance, PSP — which are common and cheap unless they are a rare colourway or region. Genuine oddities such as the Watara Supervision, sold in small numbers against Nintendo and now hard to find working. And modern limited re-releases: Sega\'s Game Gear Micro sold in Japan only in small quantities, and special-edition Steam Decks, which are new hardware collected on release. Condition here means "does it work", because these are electronics: screens develop dead lines, batteries corrode contacts, and capacitors dry out.',
    glossary: [
      { term: 'IPS mod', definition: 'A replacement backlit screen fitted to an old handheld. Makes it far nicer to use and usually LOWERS collector value, since it is no longer original.' },
      { term: 'Battery corrosion', definition: 'Leaked alkaline cells eating the contacts. The single most common reason a stored handheld does not power on.' },
      { term: 'Region', definition: 'Japan-only hardware is common in this category — the Game Gear Micro at €1,357–€1,359 never launched in the West.' },
      { term: 'CIB', definition: 'Complete in box with inserts and manual. For handhelds the box is thin card and rarely survived.' },
    ],
    care:
      'Take the batteries out of anything you are storing — corrosion is what kills these, and it is avoidable. Keep units out of sunlight, which yellows old grey plastic permanently, and out of damp, which reaches the board. If a handheld has not been powered in years, inspect the battery compartment before you insert cells. Original screens scratch easily, so store in a case rather than loose in a drawer.',
    watchOut: {
      title: 'Modded units sold as original, and yellowed plastic "restored"',
      body: 'A backlit IPS screen, a replaced shell or a recapped board all change what you are buying — often for the better as a user, always for the worse as a collector — and are frequently not disclosed. Ask directly whether anything has been replaced. Separately, "retrobrite" treatment reverses yellowing chemically but weakens the plastic and often reverts; a suspiciously perfect white shell on a 30-year-old handheld deserves a question.',
    },
    valueDrivers:
      'Rarity of the specific model and colourway, then region — Japan-only hardware dominates our top rows. Then working condition and originality, then box. Modern limited runs behave differently from vintage: a Game Gear Micro or a limited Steam Deck is scarce because the maker chose a number, and it stays scarce because there is no reason to make more.',
    holyGrail: {
      title: 'Tamagotchi Pix Party (Confetti)',
      why: 'About €1,973 — and it is a virtual pet, not a games console. A short production run of a colour variant, in a line whose buyers mostly opened and used them, which is how something recent and mass-market ends up at the top of a retro category.',
    },
    entryLevel: {
      title: 'A tested Game Boy Advance or DS Lite',
      why: 'Half of what we track is under €48. Mainstream handhelds are plentiful, cheap and genuinely fun, and buying a tested working one teaches you what to check — screen lines, battery contacts, button response — before you spend on anything scarce.',
    },
  },

  plush_collectibles: {
    intro:
      'Plush collecting spans Squishmallows, Beanie Babies, Steiff bears and artist collaborations. The typical plush we track is €18 — the cheapest median in the app — and the top is €1,190.',
    whatItIs:
      'Four quite different markets share a shelf. Squishmallows are a current mass-market line where scarcity comes from short retail runs and a very active online community, and where a common plush costs €10 while a hunted one reaches four figures. Beanie Babies are the historical cautionary tale: a 1990s speculative bubble whose collapse is the reason people are sceptical about plush as an asset, though genuine early-generation tag variants do still trade meaningfully. Steiff is the opposite — a German maker since 1880, producing limited numbered bears aimed at adults from the start. And then artist and designer plush, such as KAWS, which price as art objects. Tags matter enormously across all four, because a plush without its original tag is worth a fraction of one with it.',
    glossary: [
      { term: 'Tag generation', definition: 'Which version of the maker\'s hang tag and tush tag a plush carries. On Beanie Babies this decides value — a 2nd-gen Pinchers is €346 here.' },
      { term: 'Squad', definition: 'A themed Squishmallows release. Collectors chase specific squads and specific numbered characters within them.' },
      { term: 'Steiff button-in-ear', definition: 'The metal tag in the ear, present since 1904 and the maker\'s authentication mark.' },
      { term: 'NWT', definition: 'New with tags. The benchmark condition — a detached tag is a permanent value loss.' },
    ],
    care:
      'Keep tags attached and protected — a tag protector costs almost nothing and preserves most of the value. Light fades dyed fabric quickly, so display out of the sun, and dust is abrasive on plush fibre. Never machine wash a collectable plush: it mats the fabric, wrecks the tag and can shift the stuffing permanently. For older bears, moths are a real risk; store with cedar rather than in sealed plastic, which traps moisture.',
    watchOut: {
      title: 'The Beanie Baby lesson, and counterfeit tags',
      body: 'Most plush is worth what it cost, and the 1990s Beanie bubble is the standing proof — people paid four figures for mass-produced toys on the belief that scarcity was coming, and it never was. Buy because you like the object. Where money is involved, counterfeit tags are the specific fraud: reproduction hang tags are easy to print and are routinely attached to common plush to fake an early generation.',
    },
    valueDrivers:
      'Tags first — presence, generation and condition. Then genuine short runs: the top of our catalogue is Squishmallows at €1,190 and €583, both from small retail releases with heavy community demand. Then maker, with Steiff limited editions holding value steadily rather than spiking. Artist collaborations price on the artist. Age on its own drives almost nothing here.',
    holyGrail: {
      title: 'Maxie the Mushroom Green (Squishmallows, 12")',
      why: 'About €1,190 — a current mass-market plush, not an antique. A short run plus an intensely active collecting community is enough to put a soft toy above most vintage bears, which tells you how much of this category is demand rather than scarcity.',
    },
    entryLevel: {
      title: 'A current plush you actually want to own',
      why: 'Half of what we track is under €18. This is the cheapest category in the app to start, and the one where buying for love rather than return is most obviously the right approach — the history of plush speculation is not encouraging.',
    },
  },

  jp_magazine: {
    intro:
      'Japanese manga magazines are disposable weeklies that occasionally turn out to be historic documents. The typical issue we track is €44, and the top is €26,205.',
    whatItIs:
      'Manga is serialised first in fat, cheap weekly or monthly anthologies — Weekly Shonen Jump above all — printed on newsprint that yellows within a year and thrown out by nearly everyone once read. Volumes come later; the magazine is where a series actually begins. That makes first-chapter issues genuinely rare artefacts: the issue containing chapter one of Dragon Ball had no reason to be kept by anyone. Alongside the manga magazines sit the children\'s monthlies, above all CoroCoro Comic, which for decades has bundled promotional trading cards — including Pokémon promos that were only ever obtainable by buying that month\'s issue. Those inserts are collected as cards, in a category most people never think to look in.',
    glossary: [
      { term: 'First chapter issue', definition: 'The magazine containing chapter one of a series. The Dragon Ball debut is €26,205 in our catalogue — an object nobody was meant to keep.' },
      { term: 'CoroCoro insert', definition: 'A promotional card bundled with the monthly. The 1990s Ancient Mew and Shiny Mew promos sit near €875 each.' },
      { term: 'Shikishi', definition: 'A square art board, often signed. A Toriyama-signed Dragon Ball board is about €4,712 here.' },
      { term: 'Yakeru / yellowing', definition: 'The newsprint browning that affects every one of these. Condition language is relative — an unyellowed 1984 issue effectively does not exist.' },
    ],
    care:
      'Newsprint is acidic and destroys itself: store issues flat, in acid-free bags with boards, out of light and humidity, and never stacked under weight. Do not attempt to flatten or clean a magazine, and never remove an insert card from an unopened issue — a sealed issue with its promo still inside is worth substantially more than the two parts separated. Handle with clean dry hands; the paper is fragile enough to tear at the spine from ordinary reading.',
    watchOut: {
      title: 'Reprints, bound volumes and removed inserts',
      body: 'Popular first chapters have been reissued in anniversary editions and bound reprints that look similar in a listing photo — check the date on the cover and the spine, not the artwork. For CoroCoro, the frequent trick is an issue sold as complete with the promo card already removed, or a loose promo presented as if it came from a sealed issue. Ask for photos of the cover date and the insert in place.',
    },
    valueDrivers:
      'Whether the issue contains a first chapter of something that became enormous, then condition, which for newsprint means relative rather than absolute. Then inserts: a CoroCoro with its promo card intact is priced as magazine plus card. Signed shikishi and event boards form their own tier. Ordinary issues of even famous magazines are worth a few euros, which is the normal case — this category is a handful of documents and a very long cheap tail.',
    holyGrail: {
      title: 'Monthly Shonen Jump — Dragon Ball first chapter',
      why: 'About €26,205. A cheap 1984 magazine printed to be read on a train and thrown away, which happens to contain the opening pages of the most influential manga ever serialised. Nothing about it was collectable at the time, which is exactly why so few survive.',
    },
    entryLevel: {
      title: 'A recent issue of a magazine you read',
      why: 'Half of what we track is under €44 and current issues cost a few euros imported. Buy one to see what the format actually is — the paper quality alone explains why the old ones are rare.',
    },
  },

  keycaps: {
    intro:
      'Custom keycaps are made in group buys, produced once, and never restocked. The typical set we track is €60, and complete custom builds reach €1,750.',
    whatItIs:
      'The mechanical keyboard hobby buys its parts through GROUP BUYS: a designer proposes a colourway, people commit money, the manufacturer runs exactly that quantity months later, and the mould is retired. There is no restock and no second chance, which is why sets trade above retail immediately after shipping. Names encode the profile — the shape of the cap in cross-section — with GMK, KAT, SA and Cherry being the common ones, and a set from one profile is not interchangeable with another. Sets are sold as a BASE KIT covering a standard keyboard plus optional kits for unusual layouts, so "does it support my board" is a real question rather than a formality. Around caps sits the same economy in switches, cases and artisan single caps.',
    glossary: [
      { term: 'Group buy (GB)', definition: 'The pre-order model that defines this hobby: pay up front, receive months later, quantity fixed by how many joined.' },
      { term: 'Profile', definition: 'The keycap shape — GMK (Cherry), KAT, SA, MT3. Determines feel and whether a set matches your board visually.' },
      { term: 'Base kit', definition: 'The core set covering a standard layout. Non-standard boards need the extra kits, which sell out separately.' },
      { term: 'Artisan', definition: 'A single hand-cast decorative cap, often resin. Jelly Key\'s Arcade Cabinets pieces are around €871 for one key.' },
    ],
    care:
      'ABS keycaps develop a greasy shine with use and it cannot be reversed — rotate sets or accept it as patina. Wash caps in lukewarm water with mild soap and dry fully before refitting; never put them in a dishwasher, which warps and fades legends. Keep sets out of sunlight, since UV yellows lighter ABS permanently, and store them in their trays rather than loose in a bag, where the stems chip.',
    watchOut: {
      title: 'Clones, and buying kits that do not fit your board',
      body: 'Popular colourways are cloned in cheaper plastic with slightly wrong legends and sold as the original — check the manufacturer\'s stamp on the underside and buy from the community marketplaces where reputations exist. The commoner and more expensive mistake is fit: buying a base kit that does not cover your board\'s layout, then discovering the extension kit was a separate group buy that ended two years ago.',
    },
    valueDrivers:
      'Whether the group buy is closed and how small it was, then the colourway\'s standing in the community, then profile — GMK and KAT sets dominate the top of our catalogue. Completeness matters enormously: base kit plus the matching extras sells far above a base kit alone. Full custom builds (case, plate, switches, caps assembled) top the list at €1,750, because they bundle several closed group buys into one object.',
    holyGrail: {
      title: 'TGR Alice — full build',
      why: 'About €1,750 — a complete keyboard rather than a set of caps, built from parts that each came from a closed group buy. In a hobby where nothing is ever reproduced, an assembled board is several extinct runs in one object.',
    },
    entryLevel: {
      title: 'An in-stock set from a maker that does regular restocks',
      why: 'Half of what we track is under €60, and several manufacturers now keep popular colourways in stock permanently. Buy one, live with the profile for a month, and learn what you actually like before committing money to a group buy that ships next year.',
    },
  },

  whiskey: {
    intro:
      'Whisky collecting is about bottles that were distilled decades before anyone thought to keep them. The typical bottle we track is €23, and the top is a Japanese single malt at €1,433.',
    whatItIs:
      'The label states an AGE — the youngest whisky in the bottle — and that number is the hobby\'s central fact: a 25 year old was distilled 25 years before bottling, so a distillery cannot respond to demand except by waiting. Japanese whisky is the clearest case: global demand outran the stock laid down in the 1990s, so Nikka and Suntory withdrew most age-stated bottlings, and the ones already on shelves became the entire supply forever. Alongside distillery bottlings sits an independent-bottler market — companies buying casks and releasing them under their own labels, often single-cask and numbered in the hundreds. Two things matter physically: the fill level, which drops as the cork ages, and whether the bottle has ever been opened, because an opened bottle is drink rather than stock.',
    glossary: [
      { term: 'Age statement', definition: 'The age of the YOUNGEST whisky in the bottle. Withdrawn age statements are the main source of scarcity — Nikka Yoichi 15 is €1,433 here.' },
      { term: 'Independent bottler', definition: 'A company bottling casks bought from distilleries, often single cask and numbered. That Boutique-y Ardbeg is about €1,252.' },
      { term: 'Fill level', definition: 'How high the liquid sits. Evaporation past the shoulder signals a failing cork and cuts value sharply.' },
      { term: 'OB vs IB', definition: 'Official (distillery) bottling versus independent. They price differently for the same distillery and year.' },
    ],
    care:
      'Store bottles UPRIGHT — unlike wine, high-strength spirit degrades a cork it sits against, and a failed cork means evaporation and a ruined bottle. Keep them cool, dark and stable; sunlight bleaches both label and liquid, and the label is a large part of the value. Do not refrigerate, do not display under spotlights, and if a cork looks dry, keep the bottle upright and consider re-waxing rather than laying it down.',
    watchOut: {
      title: 'Refills, fake labels and the "investment" pitch',
      body: 'The specific fraud is a genuine empty bottle refilled with cheaper spirit and resealed — check the seal, the fill level and the cap for tampering, and buy rare bottles from auction houses that authenticate. Be equally sceptical of cask-investment schemes marketed to collectors: they are a different asset with different risks from a bottle you own outright, and the resale route is far less liquid than the sales pitch suggests.',
    },
    valueDrivers:
      'Whether the expression is discontinued — withdrawn age statements do most of the work — then distillery reputation, with Japanese single malts commanding a premium no other region matches for the same age. Then bottling series and cask type, then fill level and label condition. Note the shape of our catalogue: the median is €23 because most whisky is made to drink, and the collectable end is a narrow band of withdrawn bottlings.',
    holyGrail: {
      title: 'Nikka Yoichi 15 Year Old',
      why: 'About €1,433. Withdrawn when Nikka ran out of aged stock, so no more can exist until whisky distilled today is old enough — which is fifteen years of guaranteed scarcity that no amount of demand can shorten.',
    },
    entryLevel: {
      title: 'A current no-age-statement bottle you want to drink',
      why: 'Half of what we track is under €23. Buy something you will open: the difference between a collector and a hoarder here is that the collector knows what the liquid tastes like, and you cannot learn that from a sealed bottle.',
    },
  },

  vtuber: {
    intro:
      'VTuber merchandise is sold in short online windows tied to anniversaries and live events. The typical item we track is €64, and the top is an indie acrylic stand at €639.',
    whatItIs:
      'VTubers are streamers who perform as animated characters, organised mostly into agencies — Hololive is the largest — with a long tail of independents. Merchandise follows the streaming calendar rather than a retail one: an anniversary, a birthday, a live concert or a graduation triggers a limited order window, usually a few weeks, usually Japan-only, and then the item is never made again. Because the audience is global and the shop is not, proxy buying is normal. The objects themselves are mostly light and printed — acrylic stands, tapestries, plush, signed shikishi boards — so this is a category where scarcity comes entirely from the sales window rather than from materials, and where a graduated (retired) talent\'s goods stop being produced permanently the day they stop streaming.',
    glossary: [
      { term: 'Anniversary / birthday goods', definition: 'Merchandise sold in a short window around a date. The Gawr Gura 4th anniversary tapestry is about €602 here.' },
      { term: 'Graduation', definition: 'When a talent retires the character. Merchandise ends permanently, which is the sharpest scarcity event in this hobby.' },
      { term: 'Acrylic stand', definition: 'A printed acrylic figure on a base — the standard cheap merch item, and the format most often limited.' },
      { term: 'Shikishi', definition: 'A square art board, sometimes hand-signed. A signed Houshou Marine board is around €555.' },
    ],
    care:
      'Almost everything here is printed and fades: keep tapestries and acrylics out of direct sunlight, which washes the colours within months on a sunny wall. Acrylic scratches easily, so keep the protective film on until display and store stands in sleeves. Fabric goods should be kept dry and out of light; plush attract dust and cannot be washed without matting. Keep the packaging for anything you might resell — for limited goods the sealed bag is part of the item.',
    watchOut: {
      title: 'Bootlegs and proxy costs',
      body: 'Unofficial acrylics and tapestries are printed at scale and sold on general marketplaces at a fraction of the price — the tells are colour saturation, print resolution on fine lineart, and missing official holograms or shop tags. Buy from the agency shops or established proxies. And do the arithmetic before committing: proxy fee, domestic shipping, international shipping and customs frequently exceed the item price on a €30 acrylic stand.',
    },
    valueDrivers:
      'How short the order window was, then whether the talent has graduated, then the format — signed boards and large tapestries above small acrylics. Agency matters less than individual popularity: our top item is an INDIE talent\'s anniversary stand at €639, above several Hololive pieces, because independents produce in far smaller numbers.',
    holyGrail: {
      title: 'Shylily 3rd Anniversary acrylic stand',
      why: 'About €639 for a printed acrylic — from an independent VTuber whose merchandise runs are a fraction of an agency\'s. It shows the rule cleanly: in this category the audience size sets demand, but the order window sets supply, and the window is what prices it.',
    },
    entryLevel: {
      title: 'Current goods from a streamer you actually watch',
      why: 'Half of what we track is under €64 and most current merch is ordinary shop price. Buy from someone whose streams you enjoy — this is a category built on attachment to a performer, and nothing else about it makes sense as a purchase.',
    },
  },

  anime_bluray: {
    intro:
      'Anime on disc is collected because licences expire and printings stop. The typical release we track is €50, and the top is an out-of-print Western edition at €800.',
    whatItIs:
      'A series is licensed to a distributor for a fixed term and a fixed region. When the term ends the discs stop being pressed, and if nobody re-licenses it, that edition is the last one — which is why an ordinary Blu-ray of a well-liked show can reach three figures while the show itself streams somewhere. Western boutique labels (Discotek, Sentai, Aniplex USA) release small runs with restoration work and extras; Japanese domestic releases are a separate market again, priced far higher at retail and usually region-locked to Japan. Region coding matters more here than in most disc collecting, because a Japanese Blu-ray is region A and a European one region B, and the sets people most want are often the ones that never left Japan.',
    glossary: [
      { term: 'OOP', definition: 'Out of print — the licence lapsed and the discs stopped. The main reason anything here is expensive.' },
      { term: 'Region lock', definition: 'Blu-ray regions A (Japan/US), B (Europe), C. A Japanese import will not play on an unmodified European machine.' },
      { term: 'Boutique label', definition: 'Discotek, Sentai and similar — small runs, restored transfers, often the only Western release a title ever gets.' },
      { term: 'LE / artbox', definition: 'A limited edition with a rigid box, booklet or soundtrack. Usually the version that holds value.' },
    ],
    care:
      'Discs rot: keep them out of heat and humidity, stored vertically, and never leave them in a car or an attic. The packaging is most of the value on limited editions, so keep artboxes out of sunlight (spines fade fastest) and support them upright rather than stacked. Handle discs by the edge, and if a set includes a booklet, keep it inside the box rather than loose where it creases.',
    watchOut: {
      title: 'Bootleg box sets and region assumptions',
      body: 'Cheap "complete series" box sets of expensive out-of-print shows are overwhelmingly bootlegs — printed covers, no distributor logo, poor transfers, and prices well below the market. Check for the licensor\'s logo and the disc pressing quality. Second, confirm the region before importing: a Japanese set you cannot play is an expensive shelf ornament unless you have a region-free player.',
    },
    valueDrivers:
      'Out-of-print status first, then how loved the series is relative to how small the print run was — the top of our catalogue is a Sentai release at €800 for a show that streams widely, purely because the discs stopped. Then edition: limited artbox releases above standard. Then condition of packaging, then whether it is a Japanese domestic release, which carries its own premium and its own region problem.',
    holyGrail: {
      title: 'No Game No Life (Blu-ray, Sentai)',
      why: 'About €800 for a modern Western Blu-ray of a series that is not rare, not old and not obscure. It is the purest illustration of this category: nothing about the show is scarce, only the licence — and licences simply expire.',
    },
    entryLevel: {
      title: 'A current-licence release of a series you love',
      why: 'Half of what we track is under €50, and in-print releases sit at normal retail. Buy the show you rewatch: this is a category where the thing you bought to enjoy quietly becomes scarce on its own, and the ones bought purely to flip mostly do not.',
    },
  },

  one_piece: {
    intro:
      'One Piece merchandise beyond the card game — sealed product, figures, licensed collaborations. The typical item we track is €32, and the top is an alternate-art card at €1,734.',
    whatItIs:
      'A franchise running since 1997 with an unusually broad merchandise economy, and this category is the part of it that is not the trading card game proper (which has its own guide). In practice it holds three things. Sealed TCG product — booster boxes people bought to keep rather than open, where OP01 Romance Dawn tops the list because the early English print runs were tiny. Chase singles that trade alongside general merchandise rather than in the card market. And licensed collaborations, which is where the franchise\'s reach shows: a Casio G-Shock built around the Straw Hat crew sits at about €1,051, priced as a watch and as merchandise at once. The unifying rule is that One Piece never goes out of print as a story, so scarcity is always about a specific manufactured run rather than about the property cooling off.',
    glossary: [
      { term: 'Sealed box', definition: 'An unopened booster box, bought as stock rather than to play. OP01 Romance Dawn is about €1,613 here.' },
      { term: 'Alt art / SEC', definition: 'Alternate-art and secret-rare cards that trade as collectibles — the Gear 4 Luffy is €1,734.' },
      { term: 'Collaboration', definition: 'A licensed crossover product (G-Shock, apparel, homeware). Priced on both brands, and usually a single limited run.' },
      { term: 'Ichiban Kuji', definition: 'The Japanese prize-lottery line — a large source of One Piece figures that were never sold at a fixed price.' },
    ],
    care:
      'Sealed boxes are the fragile asset: keep them out of sun and damp, never stack weight on them, and accept that a dented box is discounted even though the cards inside are untouched. Licensed collaboration goods should keep their packaging and papers, which for something like a watch is a large share of resale. Figures and resin follow the usual rules — out of direct light, away from heat.',
    watchOut: {
      title: 'Resealed boxes and the collaboration premium',
      body: 'Sealed TCG product is resealed and passed off as factory-sealed often enough that experienced buyers photograph the seams and weigh the box; buy from specialists rather than general marketplaces. On collaborations, be clear about what you are paying for: a licensed watch is worth what the watch is worth plus a franchise premium that can evaporate, and it is not the same asset as a scarce printed card.',
    },
    valueDrivers:
      'For sealed product, print run and set — the earliest English sets dominate. For singles, alternate art and secret rarity. For collaborations, the partner brand\'s own standing plus the size of the run. Character matters throughout, with Luffy and Ace carrying premiums that the rest of a very large cast does not.',
    holyGrail: {
      title: 'Monkey D. Luffy — OP03 SEC Gear 4 alternate art',
      why: 'About €1,734. The most famous moment of the most popular character, at the rarest treatment the game prints — a card that trades in the merchandise market as much as in the player market.',
    },
    entryLevel: {
      title: 'Current figures or a starter deck',
      why: 'Half of what we track is under €32. One Piece merchandise is produced in enormous quantity for a global audience, so almost everything current is affordable; the scarce items are specific old print runs, not the franchise.',
    },
  },

  pop_fandom: {
    intro:
      'Pop-culture fandom collecting — screen prints, signed records, crowdfunded giants — where the object is usually art rather than merchandise. The typical item we track is €42, and the top is a €3,044 print.',
    whatItIs:
      'A category defined by limited runs rather than by subject. Three engines drive it. Poster art, above all Mondo, which commissions artists to reinterpret films as screen prints in numbered editions of a few hundred — a physical print, signed and numbered, that behaves like fine art rather than a film poster. Music, where variant vinyl pressings and signed copies from artists with intense fanbases reach four figures. And crowdfunded objects like Hasbro\'s HasLab line, made once in exactly the quantity backed. What ties them together is that supply was fixed before demand was known, and no one can add to it afterwards.',
    glossary: [
      { term: 'Screen print', definition: 'A hand-pulled poster in a numbered edition, usually signed. Mondo\'s Pulp Fiction by Laurent Durieux is about €3,044.' },
      { term: 'Edition size', definition: 'The number printed, stated on the piece as e.g. 125/300. The single biggest price driver here.' },
      { term: 'Variant', definition: 'An alternative colourway of the same print, or a coloured vinyl pressing. Usually rarer than the standard.' },
      { term: 'Timed release / drop', definition: 'Sold in a short online window with no restock — the standard sales model across all three engines.' },
    ],
    care:
      'Prints are paper and behave like it: store flat or framed with UV glass and acid-free backing, never rolled long-term, and never trimmed. Sunlight fades screen-print inks permanently and that is the most common way value is lost at home. Signed vinyl should be kept out of light for the same reason — the signature fades faster than the sleeve art. Keep certificates and numbered stickers with the piece.',
    watchOut: {
      title: 'Reproductions, and signatures without provenance',
      body: 'Screen prints are photographed and reproduced as ordinary posters, which are worth nothing to a collector — check for the plate texture, the numbering in pencil, and the artist signature rather than a printed one. On signed music, a certificate proves little on its own; prefer items signed at documented events or sold directly by the artist\'s own store, and treat anonymous "hand-signed" listings with suspicion.',
    },
    valueDrivers:
      'Edition size first, then artist for prints — a Durieux or Tyler Stout carries a premium regardless of the film. Then the property\'s standing, then condition, which for paper means unrolled, untrimmed and unfaded. Crowdfunded items behave differently again: the HasLab Sail Barge at €2,361 is priced by the fact that it was made once, in the number of people who paid up front.',
    holyGrail: {
      title: 'Mondo Pulp Fiction — Laurent Durieux screen print',
      why: 'About €3,044. A numbered, signed screen print in an edition of a few hundred, by an artist collectors follow independently of the films he illustrates — this category\'s ceiling is art-market logic wearing a film licence.',
    },
    entryLevel: {
      title: 'An open-edition print or a standard vinyl pressing',
      why: 'Half of what we track is under €42. Open-edition prints and normal album pressings cost ordinary money, hang on the same wall, and let you find out whether you care about numbering before you start chasing drops.',
    },
  },

  anime_soundtrack: {
    intro:
      'Anime soundtracks on CD — original scores, character-song collections and complete box sets. The typical release we track is €40, and the top is a Dragon Ball Z collection at €1,942.',
    whatItIs:
      'Japanese music releases work on short pressings: a soundtrack is manufactured once for the run of a series, sells to the domestic audience, and is not repressed. Because CD remained the dominant Japanese format long after it faded elsewhere, the collectable catalogue is enormous and almost entirely CD rather than vinyl. Three formats recur. The OST — the score as heard in the show. Character song collections, where voice actors record in character, which have no Western equivalent and are often the scarcest items. And complete boxes gathering a long-running series, pressed in small numbers at high prices. Composers are followed individually here: Susumu Hirasawa\'s Berserk work commands more than most series soundtracks precisely because of who wrote it.',
    glossary: [
      { term: 'OST', definition: 'Original soundtrack — the instrumental score, usually released per season.' },
      { term: 'Character song', definition: 'Songs performed by voice actors in character. A Japanese format with no Western equivalent, often short-pressed.' },
      { term: 'Complete / box set', definition: 'A multi-disc collection of a long series. The Dragon Ball Z Complete Song Collection is about €1,942.' },
      { term: 'Obi', definition: 'The paper strip wrapped around a Japanese CD case. Missing obi noticeably reduces value, and it is the first thing thrown away.' },
    ],
    care:
      'Keep the obi — that narrow paper band is part of the item and collectors check for it first. Store cases upright out of sunlight, which yellows the plastic and fades the spine that identifies the disc on a shelf. Booklets are usually thick and glossy and will cockle in damp; keep humidity stable. Handle discs by the edge, and be aware that 1990s Japanese pressings are old enough that disc rot is worth checking for before buying.',
    watchOut: {
      title: 'Missing obi, and bootleg box sets',
      body: 'A listing photographed from the front will not show whether the obi is present — ask, because it is a real part of the price. Complete-collection boxes for famous series are also widely bootlegged, with printed covers and no label markings; check for the record company logo, catalogue number and the printing quality of the booklet, and be wary of a long box set priced far below the market.',
    },
    valueDrivers:
      'Whether the pressing was short and never repeated, then composer, then completeness of a multi-disc set. Character-song collections outperform their series\' popularity because they were pressed for a narrower audience. Obi and booklet condition decide the last portion, and a Japanese release with everything intact sells well above the same discs loose.',
    holyGrail: {
      title: 'Dragon Ball Z Complete Song Collection',
      why: 'About €1,942 — a large box gathering decades of music for the series, pressed once for a domestic audience at a domestic price. Nothing about it is rare by design; it simply was never made again.',
    },
    entryLevel: {
      title: 'A current OST for a series you love, imported',
      why: 'Half of what we track is under €40, and a new soundtrack costs ordinary retail. Buy the score you actually want to listen to — this is a category where the collectable items are the ones somebody kept because they liked the music.',
    },
  },

  anime_ost_vinyl: {
    intro:
      'Anime and game soundtracks pressed on vinyl by Western boutique labels. The typical record we track is €50, and the top is a Cowboy Bebop pressing at €563.',
    whatItIs:
      'A young market, and a deliberately manufactured one. Labels such as Tiger Lab, Wayo and Black Screen licence a score that only ever existed on CD or in a game, press a few thousand copies on coloured vinyl with new artwork, sell them in a single window, and move on. The audience is partly music collectors and partly people who want the object — heavyweight gatefolds, printed inners, obi-style bands — so presentation drives price more than audio does. Video game scores sit in the same market as anime scores and are collected by the same people, which is why Okami, Dead Cells and Disco Elysium appear alongside Akira and Cowboy Bebop. Nothing here is old: the scarcity is the pressing decision, not time.',
    glossary: [
      { term: 'Boutique label', definition: 'Tiger Lab, Wayo, Black Screen and similar — small licensed runs, usually one pressing only.' },
      { term: 'Variant', definition: 'A colour or splatter version of the same record, often exclusive to one shop and pressed in the low hundreds.' },
      { term: 'Repress', definition: 'A second run. Rare in this market, and its announcement typically halves the secondary price of the first.' },
      { term: 'Gatefold', definition: 'A double sleeve that opens out. Standard for these releases and part of what buyers are paying for.' },
    ],
    care:
      'Standard vinyl care applies and matters more than usual because the sleeves are elaborate: store upright, never stacked, out of heat, in outer sleeves that protect the printed gatefold edges. Coloured vinyl is no more fragile than black but shows scuffs more; use anti-static inners rather than the paper originals. Keep any obi band or insert with the record — as with Japanese CDs, it is part of the item.',
    watchOut: {
      title: 'A repress can halve what you paid',
      body: 'Unlike vintage records, these are modern licensed pressings and the label can decide to run more. Paying a large secondary premium for something recently sold out is a bet that no repress is coming — and labels do repress popular titles. Check the label\'s own announcements before paying multiples of retail, and be aware that "limited" here means one run so far, not a promise.',
    },
    valueDrivers:
      'How small the pressing was and whether a repress happened, then the property — Cowboy Bebop, Akira and the best-loved game scores lead. Then variant scarcity, then packaging condition. Because nothing in this category is old, condition expectations are high: a used copy competes with copies that were bought, played twice and shelved.',
    holyGrail: {
      title: 'Cowboy Bebop — Ask DNA (2LP, clear)',
      why: 'About €563 for a modern record. A short clear-vinyl pressing of music from a series with a devoted audience and no history of repressing — the whole category in one object.',
    },
    entryLevel: {
      title: 'An in-print soundtrack from a label you like',
      why: 'Half of what we track is under €50 and current releases sit near that at retail. Buy one in stock rather than chasing a sold-out title at three times the price, especially given a repress can arrive at any time.',
    },
  },

  jp_event: {
    intro:
      'Japanese event goods — items that could only be obtained by attending. The typical item we track is €55, and the top is a signed voice-actor board at €1,662.',
    whatItIs:
      'Japan runs a dense calendar of ticketed events where merchandise is sold nowhere else: voice-actor birthday and fan events, Wonder Festival for garage kits, museum exclusives, anniversary concerts. Attendance is often itself limited — lottery tickets, fanclub-only sales — so an item can be capped twice over, first by who could get in and then by how many were made. Wonder Festival adds a legal quirk worth knowing: creators receive one-day permission to sell licensed garage kits, so a WonFes resin kit is a licensed product that existed for a single day. Signed items dominate the top of the market because signing sessions are attendance-limited by definition, and the Ghibli Museum sits in its own corner with cels and goods sold only inside the building.',
    glossary: [
      { term: 'Shikishi', definition: 'A square art board, frequently signed at events. The Inori Minase birthday board is about €1,662 here.' },
      { term: 'WonFes (Wonder Festival)', definition: 'A twice-yearly garage-kit event where creators get one-day licences to sell resin kits — legally a single-day product.' },
      { term: 'Garage kit (GK)', definition: 'An unpainted resin model kit, cast in small numbers by an individual sculptor rather than a company.' },
      { term: 'Fanclub / lottery ticket', definition: 'How entry to many events is allocated. Limits the buyer pool before the goods are even made.' },
    ],
    care:
      'Signed paper is the fragile core: keep shikishi and signed photos framed with UV glass or in acid-free sleeves, out of daylight, since these signatures are usually marker and fade. Resin garage kits are brittle and warp in heat — keep unbuilt kits in their boxes out of the sun, and remember that resin dust is harmful to breathe if you ever sand one. Keep event pamphlets and receipts where you have them; for event goods, provenance is most of what a buyer is checking.',
    watchOut: {
      title: 'Forged signatures and recast garage kits',
      body: 'A signature is the whole value of most items here and is trivially faked on a blank board. Prefer items with event photos, wristbands or documentation, and buy from Japanese proxies and specialists rather than open marketplaces. Garage kits are widely recast — unlicensed copies made from an original — with soft detail, bubbles and no maker markings; a recast of a one-day WonFes kit is worth very little.',
    },
    valueDrivers:
      'Whether it was signed, then how restricted attendance was, then who the performer or sculptor is. Museum exclusives hold value steadily rather than spiking. Note that our top five are four signed items and one WonFes resin kit — this is a category where the object is often ordinary and the circumstances of getting it are the entire price.',
    holyGrail: {
      title: 'Inori Minase birthday event — signed shikishi',
      why: 'About €1,662 for a signed square of card. Entry to the event was limited, the signing within it more so, and the object cannot be reproduced by anyone but the person who signed it.',
    },
    entryLevel: {
      title: 'Unsigned event pamphlets and general goods',
      why: 'Half of what we track is under €55. Pamphlets, keychains and tour goods from the same events cost very little, are genuinely from the day, and carry none of the forgery risk that makes the signed end of this category hard for a beginner.',
    },
  },

  city_pop_vinyl: {
    intro:
      'City pop is 1980s Japanese pop rediscovered worldwide through streaming, and its original pressings were never made for this audience. The typical record we track is €36, and the top is €784.',
    whatItIs:
      'A loose genre of urban, funk- and AOR-influenced Japanese pop from roughly 1978 to 1990 — Tatsuro Yamashita, Mariya Takeuchi, Anri, Seiko Matsuda — pressed for the domestic market and largely forgotten until algorithmic recommendation revived it in the 2010s. That gap is the whole story: the records were manufactured in ordinary quantities for Japanese buyers, most were never exported, and demand then arrived from a global audience forty years later with no way to increase supply except reissues. Adjacent to the originals sit two related markets: the Shibuya-kei artists of the 1990s who drew on the same sound, and modern vaporwave records that sample it, which collectors of one often buy from the other.',
    glossary: [
      { term: 'Obi', definition: 'The paper strip on Japanese records. Its presence noticeably raises value and it was the first thing most owners discarded.' },
      { term: 'Original pressing', definition: 'The 1980s Japanese release, as opposed to the recent reissues. The price gap between them is large.' },
      { term: 'Shibuya-kei', definition: 'The 1990s Japanese scene that revived the sound — Pizzicato Five, Flipper\'s Guitar — collected alongside city pop proper.' },
      { term: 'Promo / white label', definition: 'A radio or shop copy, often marked, pressed in far smaller numbers than the retail release.' },
    ],
    care:
      'Japanese pressings from this era are usually excellent quality and the sleeves are thin, so store upright with outer sleeves and never stack. Keep the obi flat with the record rather than folded inside the sleeve, where it creases. Otherwise standard vinyl care: clean properly rather than wiping, handle by the edges, and keep them away from heat, which is what warps a record that survived forty years fine.',
    watchOut: {
      title: 'Reissues sold as originals, and the streaming premium',
      body: 'Most famous city pop albums have been reissued recently, and a reissue can look nearly identical in a photo — check the runout matrix, the label design and the catalogue number rather than the cover. Be aware too that prices here follow attention: an album that goes viral can double and then settle, so paying a spike price for a record that is being repressed is the common way to lose money in this category.',
    },
    valueDrivers:
      'Original pressing status first, then obi presence, then condition of record and sleeve. Then the specific artist\'s standing with the online audience, which does not always match their standing in Japan — Flipper\'s Guitar\'s Camera Talk at €784 leads our catalogue on scarcity and cult reputation rather than chart history. Promo copies add a further premium.',
    holyGrail: {
      title: "Flipper's Guitar — Camera Talk",
      why: 'About €784. A Shibuya-kei album from a short-lived band, pressed modestly for a domestic audience and never widely exported — the ceiling here belongs to records that were obscure even in Japan, not to the hits.',
    },
    entryLevel: {
      title: 'A modern reissue of an album you already stream',
      why: 'Half of what we track is under €36, and reissues of the well-known albums are pressed properly and cost normal money. Start there: you get the music on vinyl, and you learn to read runouts and obi before paying original-pressing prices.',
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
