// ═══════════════════════════════════════════════════════════════════════════
// Sparrow Collect Category Niches — maps to 54 app categories + 8 pods
// ═══════════════════════════════════════════════════════════════════════════

export type NicheId = string;

export interface NicheInfo {
  id: NicheId;
  emoji: string;
  label: string;
  podId: string;           // Which pod owns this niche
  color: string;
  /** Key stats/facts for "Did You Know" template scripts */
  facts: string[];
  /** Price ranges for "Price Check" template scripts */
  priceExamples: { item: string; low: number; high: number }[];
}

// ─── Pod-Aligned Niches (top 15 categories + grouped) ────────────────────

export const NICHES: NicheInfo[] = [
  {
    id: "pokemon",
    emoji: "\u{1F4A0}",
    label: "Pokemon TCG",
    podId: "pokemon",
    color: "#FFD700",
    facts: [
      "A PSA 10 Base Set Charizard sold for $420,000 in 2022",
      "Pokemon is the highest-grossing media franchise ever at $150B+",
      "Only 3% of Base Set Charizards grade PSA 10",
      "Japanese promos can be worth 10x their English counterparts",
    ],
    priceExamples: [
      { item: "Base Set Charizard (PSA 10)", low: 250000, high: 420000 },
      { item: "Illustrator Pikachu", low: 900000, high: 5275000 },
      { item: "Gold Star Rayquaza", low: 5000, high: 45000 },
    ],
  },
  {
    id: "mtg",
    emoji: "\u{1FA84}",
    label: "Magic: The Gathering",
    podId: "mtg",
    color: "#8B5CF6",
    facts: [
      "A Black Lotus Alpha sold for $540,000 — the most expensive MTG card ever",
      "Only 1,100 Alpha Black Lotuses were ever printed",
      "Reserved List cards can never be reprinted, creating guaranteed scarcity",
      "MTG has over 27,000 unique cards across 100+ sets",
    ],
    priceExamples: [
      { item: "Alpha Black Lotus (BGS 9.5)", low: 300000, high: 540000 },
      { item: "Alpha Mox Sapphire", low: 15000, high: 80000 },
      { item: "Revised Dual Lands (set)", low: 3000, high: 12000 },
    ],
  },
  {
    id: "funko",
    emoji: "\u{1F47E}",
    label: "Funko Pop",
    podId: "funko",
    color: "#EC4899",
    facts: [
      "The Alex DeLarge Glow Funko sold for $13,300 on eBay",
      "Funko has produced over 20,000 unique Pop figures",
      "SDCC & NYCC exclusives average 300% markup within 6 months",
      "Vaulted Pops appreciate an average of 40% per year",
    ],
    priceExamples: [
      { item: "Alex DeLarge (Glow)", low: 8000, high: 13300 },
      { item: "Holographic Darth Maul", low: 4000, high: 8500 },
      { item: "Planet Arlia Vegeta", low: 2500, high: 5000 },
    ],
  },
  {
    id: "warhammer",
    emoji: "\u{2694}\u{FE0F}",
    label: "Warhammer 40K",
    podId: "warhammer",
    color: "#EF4444",
    facts: [
      "A pro-painted Warhammer army can sell for $5,000-$50,000",
      "Games Workshop stock has outperformed the S&P 500 for 10 years",
      "OOP metal models can be worth 10-50x their original price",
      "The global miniatures market is worth $3.5B and growing 8% annually",
    ],
    priceExamples: [
      { item: "OOP Metal Thunderhawk", low: 2000, high: 5000 },
      { item: "Pro-painted 2000pt Army", low: 3000, high: 15000 },
      { item: "Forge World Warlord Titan", low: 1500, high: 4000 },
    ],
  },
  {
    id: "sneakers",
    emoji: "\u{1F45F}",
    label: "Sneakers",
    podId: "sneakers",
    color: "#3B82F6",
    facts: [
      "The sneaker resale market is worth $10B+ globally",
      "Nike Dunk Lows saw a 1,200% price increase from 2019 to 2021",
      "Jordan 1 OG colorways hold value better than any other silhouette",
      "Deadstock condition adds 40-80% premium over VNDS",
    ],
    priceExamples: [
      { item: "Jordan 1 Chicago (DS)", low: 1500, high: 4500 },
      { item: "Nike MAG (Back to the Future)", low: 15000, high: 55000 },
      { item: "Travis Scott x Jordan 1 Low", low: 800, high: 2000 },
    ],
  },
  {
    id: "watches",
    emoji: "\u{231A}",
    label: "Watches",
    podId: "watches",
    color: "#14B8A6",
    facts: [
      "A Patek Philippe Nautilus 5711 retails at $35K but resells for $130K+",
      "Vintage Rolex Daytonas have appreciated 500% in the last decade",
      "The luxury watch market is worth $75B and growing 5% annually",
      "Full box & papers add 15-30% to a watch's resale value",
    ],
    priceExamples: [
      { item: "Rolex Daytona 116500LN", low: 25000, high: 45000 },
      { item: "Patek Philippe Nautilus 5711/1A", low: 100000, high: 180000 },
      { item: "Omega Speedmaster Moonwatch", low: 5000, high: 8000 },
    ],
  },
  {
    id: "vinyl",
    emoji: "\u{1F3B5}",
    label: "Vinyl Records",
    podId: "vinyl",
    color: "#F97316",
    facts: [
      "Vinyl outsold CDs for the first time since 1987 in 2023",
      "A sealed Beatles 'Yesterday and Today' butcher cover sold for $125K",
      "First pressings can be worth 100x a reissue",
      "City pop vinyl from the 80s has surged 400% since 2020",
    ],
    priceExamples: [
      { item: "Beatles Butcher Cover (sealed)", low: 50000, high: 125000 },
      { item: "Wu-Tang 'Once Upon a Time' (1/1)", low: 1000000, high: 2000000 },
      { item: "Mariya Takeuchi 'Variety' (OG)", low: 200, high: 800 },
    ],
  },
  {
    id: "lego",
    emoji: "\u{1F9F1}",
    label: "LEGO",
    podId: "general",
    color: "#81D8D0",
    facts: [
      "Retired LEGO sets appreciate an average of 11% per year — better than gold",
      "The UCS Millennium Falcon (75192) retails at $850 and resells for $1,200+",
      "Sealed LEGO sets from 2000-2015 have outperformed the S&P 500",
      "Minifigure-heavy sets hold value better than vehicle sets",
    ],
    priceExamples: [
      { item: "UCS Millennium Falcon (10179, sealed)", low: 5000, high: 15000 },
      { item: "Cafe Corner (10182, sealed)", low: 3000, high: 6000 },
      { item: "Mr. Gold Minifigure", low: 2000, high: 5000 },
    ],
  },
  {
    id: "hot_toys",
    emoji: "\u{1F9F8}",
    label: "Hot Toys",
    podId: "general",
    color: "#81D8D0",
    facts: [
      "Hot Toys figures can take 6-18 months from announcement to delivery",
      "Sideshow exclusive variants command 50-200% premiums after selling out",
      "A complete Marvel lineup (50+ figures) can exceed $30,000 in value",
      "DX-series figures with LED light-up features appreciate fastest",
    ],
    priceExamples: [
      { item: "DX19 Dark Knight Joker", low: 800, high: 2500 },
      { item: "Iron Man Mark LXXXV (BD)", low: 400, high: 900 },
      { item: "Mandalorian & Grogu Set", low: 500, high: 1000 },
    ],
  },
  {
    id: "yugioh",
    emoji: "\u{1F0CF}",
    label: "Yu-Gi-Oh!",
    podId: "general",
    color: "#81D8D0",
    facts: [
      "A PSA 10 Tournament Black Luster Soldier sold for $2M in 2022",
      "Ghost Rare cards from older sets can be worth $1,000+",
      "Starlight Rares have a pull rate of roughly 1 per 2 cases",
      "Quarter Century Secret Rares are the newest ultra-premium chase cards",
    ],
    priceExamples: [
      { item: "Tournament Black Luster Soldier", low: 1500000, high: 2000000 },
      { item: "Blue-Eyes White Dragon (LOB 1st)", low: 5000, high: 50000 },
      { item: "Ghost Rare 1st Ed Stardust Dragon", low: 800, high: 3000 },
    ],
  },
  {
    id: "kpop",
    emoji: "\u{1F3A4}",
    label: "K-pop Merch",
    podId: "general",
    color: "#81D8D0",
    facts: [
      "BTS photocards can sell for $500-$5,000+ for rare POB versions",
      "The K-pop merch market exceeded $1.2B in 2024",
      "Album pre-order benefit (POB) cards are the most sought-after items",
      "Complete photocard sets from limited runs can exceed $10,000",
    ],
    priceExamples: [
      { item: "BTS V Lucky Draw PC", low: 1000, high: 5000 },
      { item: "NewJeans Bluebook POB Set", low: 200, high: 800 },
      { item: "aespa Synk Dive Lightstick (signed)", low: 300, high: 1500 },
    ],
  },
  {
    id: "manga",
    emoji: "\u{1F4DA}",
    label: "Manga",
    podId: "general",
    color: "#81D8D0",
    facts: [
      "First print Chainsaw Man Vol. 1 in Japanese is worth 50x cover price",
      "OOP manga sets (Slam Dunk, Vagabond) can sell for $500-$2,000",
      "The manga market hit $13.1B globally in 2023",
      "Signed manga from Jump Festa can be worth 100x unsigned",
    ],
    priceExamples: [
      { item: "Berserk Vol 1-41 (complete)", low: 400, high: 1200 },
      { item: "Dragon Ball 1st Print Vol 1", low: 200, high: 1000 },
      { item: "One Piece Box Set 1-4", low: 500, high: 900 },
    ],
  },
];

/** Lookup by niche ID */
export function getNiche(id: string): NicheInfo | undefined {
  return NICHES.find((n) => n.id === id);
}

/** Get all niches for a specific pod */
export function getNichesByPod(podId: string): NicheInfo[] {
  return NICHES.filter((n) => n.podId === podId);
}
