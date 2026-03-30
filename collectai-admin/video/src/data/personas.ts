/**
 * Audience Personas — Who We're Talking To
 *
 * These personas drive content targeting, hook selection, and CTA matching.
 * The learning loop evaluates which persona a video resonates with
 * based on engagement patterns.
 */

export interface CollectorPersona {
  id: string;
  name: string;
  /** One-sentence summary */
  headline: string;
  /** Demographic sketch */
  demographics: {
    ageRange: string;
    gender: string;
    income: string;
    location: string;
  };
  /** What drives them psychologically */
  psychographics: {
    motivation: string;
    identity: string;
    socialBehavior: string;
    spendingPattern: string;
    riskTolerance: string;
  };
  /** Collection characteristics */
  collectionProfile: {
    size: string;
    value: string;
    niches: string[];
    trackingMethod: string;
    buyingFrequency: string;
  };
  /** Content that hooks this persona — mapped to our content angles */
  contentTriggers: Array<{
    trigger: string;
    why: string;
    bestAngle: string;
  }>;
  /** Objections to using CollectAI — and how to overcome them */
  objections: Array<{
    objection: string;
    reframe: string;
    proofPoint: string;
  }>;
  /** How this persona discovers and installs apps */
  conversionPath: {
    discoveryChannel: string;
    decisionDriver: string;
    activationMoment: string;
    retentionHook: string;
  };
  /** TikTok/Reels behavior */
  platformBehavior: {
    watchTime: string;
    engagementStyle: string;
    followsAccountsLike: string;
    sharesTrigger: string;
  };
}

export const COLLECTOR_PERSONAS: CollectorPersona[] = [
  // ═══════════════════════════════════════════════════════════════
  // PERSONA 1: THE TREASURE HUNTER
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'treasure_hunter',
    name: 'The Treasure Hunter',
    headline: 'Lives for the thrill of finding undervalued items at garage sales, thrift stores, and flea markets.',
    demographics: {
      ageRange: '22–38',
      gender: '65% male, 35% female',
      income: '$35K–$75K — not rich, but finds money in the hunt',
      location: 'Suburban US/UK/EU — access to garage sales, estate sales, thrift stores',
    },
    psychographics: {
      motivation: 'The dopamine of discovering something worth 50x what they paid',
      identity: 'Sees themselves as a savvy finder — "I have the eye"',
      socialBehavior: 'Loves telling stories about finds — natural content sharers',
      spendingPattern: 'Spends little per item ($1–$50) but buys frequently',
      riskTolerance: 'Low per-item risk (cheap buys), high cumulative spend',
    },
    collectionProfile: {
      size: '50–500 items across multiple niches',
      value: '$2K–$25K (often doesn\'t know the exact number)',
      niches: ['pokemon', 'retro_games', 'vinyl', 'funko', 'lego', 'vintage_toys'],
      trackingMethod: 'Barely tracks — maybe a mental list or nothing at all',
      buyingFrequency: 'Weekly — always checking local sources',
    },
    contentTriggers: [
      {
        trigger: 'Hidden gem reveals — "$3 at Goodwill, actually worth $400"',
        why: 'Validates their hobby and teaches them what to look for',
        bestAngle: 'deal_hunting',
      },
      {
        trigger: 'Scanning and identifying unknown items — "Is this worth anything?"',
        why: 'Their biggest pain point — standing in a thrift store not knowing if something is valuable',
        bestAngle: 'ai_magic',
      },
      {
        trigger: 'Price comparison across marketplaces — "Where to sell this for the most"',
        why: 'They flip finds, so knowing the best selling channel is critical',
        bestAngle: 'market_intelligence',
      },
    ],
    objections: [
      {
        objection: '"I can just Google it"',
        reframe: 'Try Googling the exact variant, condition, and current market price for 20 items at a garage sale',
        proofPoint: 'Side-by-side: Google search (30s per item, vague results) vs. CollectAI scan (3s, exact price)',
      },
      {
        objection: '"Free apps already do this"',
        reframe: 'Name one that searches 37 marketplaces and gives you comps from eBay, TCGPlayer, Cardmarket, and StockX simultaneously',
        proofPoint: 'Show search results across 6+ sources in one screen',
      },
      {
        objection: '"I don\'t have enough items to justify an app"',
        reframe: 'You don\'t need 1,000 items — even 5 items might surprise you. One scan takes 3 seconds.',
        proofPoint: '"I scanned just 5 items and found out my $20 finds are worth $380 total"',
      },
    ],
    conversionPath: {
      discoveryChannel: 'TikTok/Reels — garage sale hauls and thrift finds',
      decisionDriver: 'Seeing the app identify something they\'d find in the wild',
      activationMoment: 'First scan of an item they already own → surprise at value',
      retentionHook: 'Portfolio value growing as they add finds → "my treasure map"',
    },
    platformBehavior: {
      watchTime: 'High — watches full videos of reveals and hauls',
      engagementStyle: 'Comments "Where did you find this?!" and shares to collector friends',
      followsAccountsLike: 'Thrift store flippers, garage sale haul channels, "what\'s it worth" content',
      sharesTrigger: 'Surprising price reveals — "You won\'t believe what this is worth"',
    },
  },

  // ═══════════════════════════════════════════════════════════════
  // PERSONA 2: THE PORTFOLIO BUILDER
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'portfolio_builder',
    name: 'The Portfolio Builder',
    headline: 'Treats collecting as a serious alternative investment with spreadsheets and market research.',
    demographics: {
      ageRange: '28–50',
      gender: '75% male, 25% female',
      income: '$75K–$200K — significant disposable income allocated to collecting',
      location: 'Urban US/EU/Asia — access to auctions, conventions, online markets',
    },
    psychographics: {
      motivation: 'Building wealth through tangible assets they\'re passionate about',
      identity: 'Sees themselves as a sophisticated investor who happens to love the hobby',
      socialBehavior: 'Active in niche communities, attends conventions, reads market reports',
      spendingPattern: 'Fewer purchases but higher ticket — $200–$5,000 per acquisition',
      riskTolerance: 'Moderate — researches extensively before buying, diversifies across niches',
    },
    collectionProfile: {
      size: '20–200 items, carefully curated',
      value: '$10K–$250K (knows the approximate value)',
      niches: ['watches', 'pokemon', 'mtg', 'sneakers', 'hot_toys', 'vintage_toys'],
      trackingMethod: 'Spreadsheet or notes app — wants something better',
      buyingFrequency: 'Monthly — deliberate, researched purchases',
    },
    contentTriggers: [
      {
        trigger: 'Market movement data — "This category is up 23% this quarter"',
        why: 'Validates their investment thesis and informs future buys',
        bestAngle: 'market_intelligence',
      },
      {
        trigger: 'Portfolio flex — "$47K collection, here\'s my ROI"',
        why: 'Social proof that collecting can be financially rewarding',
        bestAngle: 'portfolio_flex',
      },
      {
        trigger: 'Multi-marketplace arbitrage — "Same card, $200 difference across platforms"',
        why: 'Saving money on acquisitions is ROI improvement',
        bestAngle: 'deal_hunting',
      },
    ],
    objections: [
      {
        objection: '"My spreadsheet works fine"',
        reframe: 'Your spreadsheet doesn\'t auto-update prices daily, alert you to market moves, or scan new items in 3 seconds',
        proofPoint: '"I deleted my 200-row spreadsheet after day 1 — CollectAI does it better AND keeps prices current"',
      },
      {
        objection: '"I don\'t trust AI pricing — I know my niche better"',
        reframe: 'We pull from the same sources you check manually — eBay, TCGPlayer, Cardmarket — just all at once',
        proofPoint: 'Show CollectAI price vs. recently sold comp on eBay → within 5%',
      },
      {
        objection: '"Is my data private? I don\'t want people knowing what I own"',
        reframe: 'Your collection is private by default. Only you see it. No public profiles unless you choose.',
        proofPoint: 'Settings screen showing privacy controls',
      },
    ],
    conversionPath: {
      discoveryChannel: 'YouTube long-form → TikTok clips, Reddit niche communities, collecting podcasts',
      decisionDriver: 'Seeing portfolio tracking in action with real price data',
      activationMoment: 'Adding their top 10 items and seeing total portfolio value + daily changes',
      retentionHook: 'Daily portfolio value updates + alerts when items spike or drop',
    },
    platformBehavior: {
      watchTime: 'Moderate — skips if no substance, stays for data-rich content',
      engagementStyle: 'Saves educational content, comments with market opinions, rarely shares',
      followsAccountsLike: 'Market analysis channels, collector podcasts, niche experts',
      sharesTrigger: 'Data that confirms or challenges their market view',
    },
  },

  // ═══════════════════════════════════════════════════════════════
  // PERSONA 3: THE CASUAL CURATOR
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'casual_curator',
    name: 'The Casual Curator',
    headline: 'Collects for joy, not profit — but is curious what their stuff might be worth.',
    demographics: {
      ageRange: '18–35',
      gender: '55% male, 45% female',
      income: '$25K–$60K — budget-conscious but spends on passions',
      location: 'Global — heavy on US, UK, Japan, South Korea, EU',
    },
    psychographics: {
      motivation: 'Expressing fandom identity and enjoying the aesthetic of collecting',
      identity: 'Fan first, collector second — "I just love Pokémon/LEGO/anime"',
      socialBehavior: 'Active on TikTok and Instagram, shares collection photos, joins fandom communities',
      spendingPattern: 'Regular small purchases — $10–$100, impulse-driven by new releases',
      riskTolerance: 'Low — rarely buys for investment, buys what they love',
    },
    collectionProfile: {
      size: '20–200 items, growing organically',
      value: '$500–$5K (genuinely doesn\'t know)',
      niches: ['funko', 'kpop', 'manga', 'lego', 'pokemon', 'ghibli'],
      trackingMethod: 'None — might photograph their shelf for Instagram',
      buyingFrequency: 'Weekly-monthly — whenever something catches their eye',
    },
    contentTriggers: [
      {
        trigger: 'The "wow I didn\'t know my stuff was worth that" moment',
        why: 'Surprise + validation that their hobby has tangible value',
        bestAngle: 'price_shock',
      },
      {
        trigger: 'Collection showcases — "My K-pop photocard collection"',
        why: 'Aspiration + community belonging + "I want to show mine too"',
        bestAngle: 'portfolio_flex',
      },
      {
        trigger: 'Easy, magical tech — "I just pointed my phone and it knew"',
        why: 'The "that\'s so cool" factor drives installs more than utility',
        bestAngle: 'ai_magic',
      },
    ],
    objections: [
      {
        objection: '"I\'m not a serious enough collector for this"',
        reframe: 'If you own 5 things you care about, you\'re a collector. CollectAI works whether you have 5 or 5,000.',
        proofPoint: 'Show someone scanning just 3 items and seeing a $200+ total value',
      },
      {
        objection: '"I don\'t want to think about my stuff as money"',
        reframe: 'It\'s not about selling — it\'s about knowing. Knowledge doesn\'t change how you feel about your collection.',
        proofPoint: '"Knowing my Totoro figure is worth $300 didn\'t make me want to sell it — it made me appreciate it more"',
      },
    ],
    conversionPath: {
      discoveryChannel: 'TikTok/Instagram Reels — stumbles on a satisfying scan video',
      decisionDriver: 'The "magic moment" of seeing the scan work looks fun and easy',
      activationMoment: 'First scan of something on their shelf → "oh cool, it knows what this is"',
      retentionHook: 'Building the visual collection gallery + seeing total value grow',
    },
    platformBehavior: {
      watchTime: 'High for entertaining content, low for data-heavy analysis',
      engagementStyle: 'Likes, shares, tags friends: "OMG scan your collection"',
      followsAccountsLike: 'Fandom accounts, aesthetic collection pages, unboxing channels',
      sharesTrigger: 'Visually satisfying + surprising — the scan moment, the price reveal',
    },
  },

  // ═══════════════════════════════════════════════════════════════
  // PERSONA 4: THE COMPLETIONIST
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'completionist',
    name: 'The Completionist',
    headline: 'Won\'t rest until they have every item in a set, series, or collection — obsessively tracks gaps.',
    demographics: {
      ageRange: '25–45',
      gender: '70% male, 30% female',
      income: '$50K–$120K — will spend significantly to fill gaps',
      location: 'US/EU/Japan — wherever the items are',
    },
    psychographics: {
      motivation: 'The satisfaction of completion + the hunt for the final pieces',
      identity: 'The definitive collector of [their niche] — "I have everything"',
      socialBehavior: 'Deep in niche communities, trades actively, knows other completionists',
      spendingPattern: 'Will pay premium for the last missing pieces — $500+ for a single gap-filler',
      riskTolerance: 'High for specific items they need — will pay over market to complete',
    },
    collectionProfile: {
      size: '100–2,000+ items, organized by set/series',
      value: '$5K–$100K (knows exactly what they have and what they\'re missing)',
      niches: ['pokemon', 'mtg', 'yugioh', 'manga', 'funko', 'warhammer', 'lego'],
      trackingMethod: 'Detailed lists or apps — already tracking but wants better tools',
      buyingFrequency: 'Targeted — buys when they find specific missing items',
    },
    contentTriggers: [
      {
        trigger: 'Set completion features — "How close am I to completing Base Set?"',
        why: 'Directly serves their core desire — seeing progress toward completion',
        bestAngle: 'portfolio_flex',
      },
      {
        trigger: 'Market alerts for missing items — "Your missing card just appeared for $50 under market"',
        why: 'Finding the specific items they need at good prices is their daily quest',
        bestAngle: 'market_intelligence',
      },
      {
        trigger: 'Catalog browsing — "Here\'s every card in the set, check off what you have"',
        why: 'Visual checklist scratches the completionist itch',
        bestAngle: 'education',
      },
    ],
    objections: [
      {
        objection: '"Does it track specific sets and show what I\'m missing?"',
        reframe: 'Yes — CollectAI has 46,500 catalog items across 54 categories. Mark what you own, see what\'s left.',
        proofPoint: 'Show set completion screen: "Base Set: 98/102 — 4 cards remaining" with missing items listed',
      },
      {
        objection: '"I already use [niche-specific tool]"',
        reframe: 'We connect the collection tracking with real-time pricing across 37 marketplaces — so you know what your gaps will cost',
        proofPoint: '"My missing 4 cards will cost me $2,340 total based on current market — CollectAI told me that in 2 seconds"',
      },
    ],
    conversionPath: {
      discoveryChannel: 'Niche community recommendations, Reddit posts, YouTube reviews',
      decisionDriver: 'Seeing the catalog depth + set completion tracking',
      activationMoment: 'Importing their existing collection and seeing completion percentage',
      retentionHook: 'Watching completion percentage tick up + alerts for missing items',
    },
    platformBehavior: {
      watchTime: 'High for niche-specific content, skips generic collecting content',
      engagementStyle: 'Comments with specific knowledge, saves reference content',
      followsAccountsLike: 'Set/series completionists, niche database accounts, price guide channels',
      sharesTrigger: 'Content about their specific niche — the more specific, the more likely to share',
    },
  },

  // ═══════════════════════════════════════════════════════════════
  // PERSONA 5: THE NOSTALGIA RETURNER
  // ═══════════════════════════════════════════════════════════════
  {
    id: 'nostalgia_returner',
    name: 'The Nostalgia Returner',
    headline: 'Rediscovered their childhood collection in the attic and wants to know if it\'s worth anything.',
    demographics: {
      ageRange: '30–50',
      gender: '60% male, 40% female',
      income: '$50K–$150K — has money now, had the collection then',
      location: 'US/EU — grew up with Pokemon/LEGO/comics/sports cards in the 90s-2000s',
    },
    psychographics: {
      motivation: 'Curiosity ("Is this worth anything?") + nostalgia ("I remember these!")',
      identity: 'Not a "collector" yet — they\'re a person who found old stuff',
      socialBehavior: 'Will share a surprising find on Facebook/Instagram — "Look what I found!"',
      spendingPattern: 'Currently $0 — they already own the items. May start buying again if re-engaged.',
      riskTolerance: 'Very low — exploring, not investing. Might sell if value is high.',
    },
    collectionProfile: {
      size: '10–100 items, discovered in storage',
      value: '$100–$10K (has no idea, that\'s why they\'re looking)',
      niches: ['pokemon', 'mtg', 'retro_games', 'vintage_toys', 'comics', 'sports_cards'],
      trackingMethod: 'None — just opened a dusty box',
      buyingFrequency: 'Zero currently — pure discovery phase',
    },
    contentTriggers: [
      {
        trigger: '"I found my old Pokemon cards — are they worth anything?"',
        why: 'This is literally their situation. They\'ll watch the entire video.',
        bestAngle: 'price_shock',
      },
      {
        trigger: 'Scanning items from childhood — nostalgic reaction + price surprise',
        why: 'Emotional resonance + practical value in one video',
        bestAngle: 'ai_magic',
      },
      {
        trigger: '"Your old [item] might be worth $X,000" — surprising value in common items',
        why: 'Creates urgency to check their own collection RIGHT NOW',
        bestAngle: 'deal_hunting',
      },
    ],
    objections: [
      {
        objection: '"I just want to know the value — I don\'t need a whole app"',
        reframe: 'One scan takes 3 seconds and it\'s free. You don\'t need to sign up for anything.',
        proofPoint: '"I downloaded it, scanned 5 cards, found out I was sitting on $2,000. Took 2 minutes."',
      },
      {
        objection: '"My cards are probably in bad condition"',
        reframe: 'Even played-condition vintage cards can be surprisingly valuable. Condition affects price but doesn\'t zero it out.',
        proofPoint: '"Even a PSA 4 Base Set Charizard is worth $500+"',
      },
    ],
    conversionPath: {
      discoveryChannel: 'Facebook/Instagram/TikTok — viral "I found my old cards" content',
      decisionDriver: 'Seeing someone scan old items they also owned as a kid',
      activationMoment: 'First scan of their childhood item → price appears → emotional reaction',
      retentionHook: 'Getting re-engaged with the hobby — starts buying again, uses portfolio to track',
    },
    platformBehavior: {
      watchTime: 'Very high for nostalgia content — will watch a full 60s video about old Pokemon cards',
      engagementStyle: 'Comments "I used to have this!!" — shares to childhood friends',
      followsAccountsLike: 'Nostalgia pages, "what are 90s toys worth" channels, general interest',
      sharesTrigger: 'Childhood items + surprising values — guaranteed share to group chats',
    },
  },
];

// Quick lookup
export function getPersona(id: string): CollectorPersona | undefined {
  return COLLECTOR_PERSONAS.find((p) => p.id === id);
}

/**
 * Match content angle to best persona targets.
 */
export function getPersonasForAngle(angleId: string): CollectorPersona[] {
  return COLLECTOR_PERSONAS.filter((p) =>
    p.contentTriggers.some((t) => t.bestAngle === angleId),
  );
}
