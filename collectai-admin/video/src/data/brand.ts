/**
 * CollectAI Brand Guide — Single Source of Truth
 *
 * This file feeds every script, brief, and learning evaluation.
 * Nothing ships without passing through this context.
 */

// ---------------------------------------------------------------------------
// 1. IDENTITY
// ---------------------------------------------------------------------------

export const BRAND_IDENTITY = {
  name: 'CollectAI',
  tagline: 'Track. Value. Collect.',
  oneLinePitch:
    'The AI-powered app that tells you what your collectibles are actually worth — across 37 marketplaces, 54 categories, in real time.',
  elevatorPitch:
    'CollectAI uses computer vision and machine learning to scan, identify, and price any collectible in seconds. ' +
    'It tracks your portfolio value over time, alerts you to market moves, and connects you with a community of ' +
    'serious collectors. Think Shazam for collectibles meets a Bloomberg terminal for your shelf.',
  missionStatement:
    'Make every collector feel like a market expert — whether you have 5 items or 5,000.',
  appStoreCategory: 'Lifestyle / Shopping',
  platforms: ['iOS', 'Android'] as const,
  founded: 2025,
  hq: 'Amsterdam, Netherlands',
} as const;

// ---------------------------------------------------------------------------
// 2. VOICE & PERSONALITY
// ---------------------------------------------------------------------------

export const BRAND_VOICE = {
  /**
   * Core personality traits — the "character" of CollectAI content.
   * Every piece of content should feel like it comes from this person.
   */
  personality: {
    primary: 'The knowledgeable friend who happens to know market prices',
    traits: [
      'Enthusiastic but not hype-beasty — we love collectibles genuinely',
      'Data-driven but never dry — numbers serve stories, not the other way around',
      'Inclusive — respects $20 collections as much as $20K ones',
      'Slightly nerdy — we enjoy deep cuts and obscure variants',
      'Confident but not arrogant — we show, not tell',
    ] as const,
  },

  /**
   * Tone spectrum — where we sit on each axis.
   * Use these as guardrails when writing scripts or evaluating content.
   */
  toneSpectrum: {
    formal_casual: 0.75,       // 0=formal, 1=casual → we're casual but credible
    serious_playful: 0.60,     // slightly playful, never clownish
    reserved_enthusiastic: 0.70, // noticeably enthusiastic, not manic
    technical_simple: 0.45,    // accessible but not dumbed down
    safe_edgy: 0.35,           // safe side — we never mock collectors
  },

  /**
   * Words we USE — these signal insider status and credibility.
   */
  vocabularyUse: [
    'grail', 'gem', 'chase', 'hit', 'pull', 'slab', 'raw',
    'vaulted', 'retired', 'NM', 'PSA 10', 'CGC 9.8', 'BGS Black Label',
    'comp', 'comp data', 'market value', 'portfolio', 'ROI',
    'centering', 'whitening', 'edge wear', 'surface', 'corners',
    'holo bleed', 'shadowless', 'first edition', '1st ed',
    'sealed', 'NIB', 'MIB', 'CIB', 'loose', 'lot',
    'flip', 'hold', 'spec', 'buylist', 'arbitrage',
    'pop count', 'pop report', 'census', 'registry set',
  ] as const,

  /**
   * Words we AVOID — these make us sound like marketers, not collectors.
   */
  vocabularyAvoid: [
    'revolutionary', 'game-changing', 'best-in-class', 'synergy',
    'leverage', 'ecosystem', 'disrupt', 'innovate', 'cutting-edge',
    'utilize', 'facilitate', 'maximize', 'optimize',
    'cheap', 'expensive' /* say "affordable" or "premium" */,
    'fake' /* say "counterfeit" or "replica" */,
    'worth nothing' /* every collection has value */,
    'investment advice' /* we never give financial advice */,
  ] as const,

  /**
   * Content rules — hard constraints.
   */
  rules: [
    'NEVER mock or belittle any collection, no matter how small or niche',
    'NEVER give financial or investment advice — we show data, users decide',
    'NEVER fake scan results or fabricate price data in content',
    'NEVER use "we" when talking about price movements — "the market" moves, we report',
    'ALWAYS credit the niche community (e.g., "the Pokemon community knows...")',
    'ALWAYS show the app doing real things — no mockups or fake UI',
    'ALWAYS include a specific number or stat — vague claims kill credibility',
    'NEVER start a video with the brand name — start with the hook',
    'NEVER use "link in bio" without a visual CTA overlay at the same time',
  ] as const,
} as const;

// ---------------------------------------------------------------------------
// 3. VISUAL IDENTITY — VIDEO SPECIFIC
// ---------------------------------------------------------------------------

export const VISUAL_IDENTITY = {
  colors: {
    primary: '#81D8D0',       // Tiffany Blue — the brand anchor
    primaryDark: '#5FBFB6',   // Darker tiffany for text on light
    secondary: '#0F172A',     // Navy — authority, trust
    accent: '#FFD700',        // Gold — for price reveals, grails
    danger: '#EF4444',        // Red — price drops, alerts
    success: '#10B981',       // Green — price gains, confirmations
    background: '#FFFFFF',    // Clean white
    backgroundDark: '#020617', // Dark mode navy-black
  },

  /**
   * Shot composition rules for TikTok/Reels.
   */
  shotRules: {
    format: '9:16 vertical, 1080×1920, 30fps',
    safeZone: 'Keep critical content in center 80% — TikTok UI covers edges',
    textPlacement: 'Lower third for item name/price, upper third for hook text',
    appOverlay: 'App screenshot in bottom-right corner, 25% screen width, subtle drop shadow',
    revealMoment: 'Price/value always revealed with a 0.5s pause + scale animation + sound hit',
    firstFrame: 'First frame must be mid-action or contain text hook — never a still logo',
    closingFrame: 'Last 3s: app icon + "Scan yours free" CTA + QR code or App Store badge',
  },

  /**
   * Editing pace — matched to TikTok attention patterns.
   */
  editingPace: {
    hookWindow: '0–1.5s: must deliver the hook (text + voice + visual all aligned)',
    retentionBridge: '1.5–3s: tease the payoff ("wait for the price...")',
    contentBody: '3–12s: deliver value (scan, reveal, comparison, story)',
    cta: 'Last 3–5s: natural CTA woven into content, never a hard pivot',
    cutFrequency: 'New visual every 2–3s minimum — no static shots >3s',
    textOnScreen: 'Every spoken stat must also appear as text overlay within 0.5s',
  },

  /**
   * Typography in videos.
   */
  typography: {
    hookText: { font: 'Inter Bold', size: '48–64px', color: '#FFFFFF', stroke: '2px #000000' },
    priceReveal: { font: 'Roboto Mono Bold', size: '72–96px', color: '#FFD700', stroke: '3px #000000' },
    itemName: { font: 'Inter SemiBold', size: '36–48px', color: '#FFFFFF', stroke: '1.5px #000000' },
    ctaText: { font: 'Inter Bold', size: '32–40px', color: '#FFFFFF', background: '#81D8D080' },
    caption: { font: 'Inter Regular', size: '24–32px', color: '#E2E8F0' },
  },

  /**
   * Sound design.
   */
  soundDesign: {
    hookHit: 'Punchy bass thud or "whoosh" at 0s — signals "pay attention"',
    revealSting: 'Cash register ding, coin drop, or short synth rise at price reveal moment',
    transitionSwipe: 'Quick swoosh between scenes — no dead air between cuts',
    backgroundMusic: 'Lo-fi or ambient at 15–20% volume — music serves content, never dominates',
    voiceover: 'Natural conversational tone, NOT announcer voice. Enthusiasm is earned by content, not forced.',
  },
} as const;

// ---------------------------------------------------------------------------
// 4. PRODUCT CONTEXT — what the app actually does
// ---------------------------------------------------------------------------

export const PRODUCT_CONTEXT = {
  /**
   * Core features — ranked by "wow factor" for content (best content hooks first).
   */
  features: [
    {
      id: 'quickscan',
      name: 'QuickScan',
      hook: 'Point your phone at any collectible and get a price in 3 seconds',
      detail: 'Computer vision + 46,500 catalog items + ML pricing across 37 marketplaces',
      contentAngle: 'The "magic moment" — best for reveal/reaction content',
      demoScript: 'Hold item → open app → tap scan → camera identifies → price appears with confidence %',
    },
    {
      id: 'portfolio',
      name: 'Portfolio Tracker',
      hook: 'Your entire collection\'s value, updated daily',
      detail: 'Auto-tracks price changes across all items. Shows ROI, gains/losses, tier ranking.',
      contentAngle: 'Portfolio flex — total value reveals, biggest movers',
      demoScript: 'Open portfolio tab → show total value → scroll through items → highlight top gainer',
    },
    {
      id: 'alerts',
      name: 'Market Alerts',
      hook: 'Get notified the second your collectible spikes or crashes',
      detail: 'Price drop/surge alerts, vaulted/retired notifications, auction ending alerts',
      contentAngle: 'FOMO/urgency — "my phone just exploded with alerts"',
      demoScript: 'Show notification → open alert → show price chart with spike → "glad I held"',
    },
    {
      id: 'grading',
      name: 'AI Condition Grading',
      hook: 'Grade your cards before you send them in — save $30 per submission',
      detail: 'AI detects centering, whitening, edge wear, surface defects. Suggests PSA/CGC grade.',
      contentAngle: 'Pre-screening — "should I grade this?"',
      demoScript: 'Scan card → AI marks defects → shows predicted grade → compare to manual assessment',
    },
    {
      id: 'marketplace',
      name: '37-Marketplace Search',
      hook: 'Search eBay, TCGPlayer, StockX, Cardmarket — all at once',
      detail: 'Unified search across 37 data sources with price comparison and affiliate links',
      contentAngle: 'Deal hunting — "found the same card $50 cheaper"',
      demoScript: 'Search item → results from 6+ marketplaces → compare prices → "this one\'s cheapest"',
    },
    {
      id: 'deals',
      name: 'P2P Deal Desk',
      hook: 'Trade with other collectors — no marketplace fees',
      detail: 'Make offers, counter, track shipping. Built-in trust scoring.',
      contentAngle: 'Community — "just traded with someone across the world"',
      demoScript: 'Find item → tap "make offer" → negotiate → both confirm → ship',
    },
  ] as const,

  /**
   * Key stats — use these in hooks and scripts for credibility.
   * Update these as the product grows.
   */
  stats: {
    categories: 54,
    catalogItems: '46,500+',
    marketplaces: 37,
    franchises: 13,
    currencies: 7,
    priceDataPoints: '2M+',        // total market observations
    scanAccuracy: '87%',            // average identification confidence
    priceUpdateFrequency: 'daily',
  },

  /**
   * Differentiators — what makes CollectAI different from alternatives.
   */
  differentiators: [
    {
      vs: 'Manual spreadsheets',
      advantage: 'Auto-scan + auto-price vs. hours of manual entry and Googling',
      contentProof: 'Side-by-side: scan 10 items in 30s vs. typing them into a spreadsheet',
    },
    {
      vs: 'Single-marketplace apps (TCGPlayer, Discogs)',
      advantage: '37 marketplaces in one search — find the real market price, not one platform\'s price',
      contentProof: 'Show same item: $200 on eBay, $180 on TCGPlayer, $160 on Cardmarket',
    },
    {
      vs: 'Price guide websites',
      advantage: 'AI vision scan in 3 seconds vs. manually searching and comparing',
      contentProof: 'Race: CollectAI scan vs. typing into price guide. CollectAI wins.',
    },
    {
      vs: 'No tracking at all',
      advantage: 'Most collectors have no idea what their collection is worth until they sell',
      contentProof: '"I thought my collection was worth $500. CollectAI says $2,847."',
    },
  ] as const,
} as const;

// ---------------------------------------------------------------------------
// 5. CTA ARCHITECTURE — how videos convert
// ---------------------------------------------------------------------------

export const CTA_SYSTEM = {
  /**
   * Primary CTAs — ranked by conversion intent.
   * Each video should use ONE primary CTA, matched to content type.
   */
  primaryCTAs: [
    {
      id: 'scan_yours',
      text: 'Scan yours free',
      subtext: 'Link in bio',
      bestFor: ['pull_reveal', 'whats_it_worth', 'hidden_gem'],
      conversionPath: 'video → profile → link → App Store → install → first scan',
    },
    {
      id: 'check_value',
      text: 'Check what yours is worth',
      subtext: 'Free on iOS & Android',
      bestFor: ['whats_it_worth', 'market_alert'],
      conversionPath: 'video → search App Store "CollectAI" → install → scan',
    },
    {
      id: 'track_portfolio',
      text: 'Start tracking your collection',
      subtext: 'CollectAI — link in bio',
      bestFor: ['collection_flex', 'market_alert'],
      conversionPath: 'video → profile → link → App Store → install → add items',
    },
    {
      id: 'never_overpay',
      text: 'Never overpay again',
      subtext: 'Compare 37 marketplaces free',
      bestFor: ['hidden_gem', 'market_alert'],
      conversionPath: 'video → search or link → install → marketplace search',
    },
  ] as const,

  /**
   * CTA delivery rules.
   */
  deliveryRules: [
    'CTA must feel like a natural extension of the content, not a commercial break',
    'Best pattern: "If you want to check yours..." (permission-based, not pushy)',
    'Show the app doing the thing you just talked about — proof before ask',
    'QR code overlay for 3s minimum — TikTok users screenshot these',
    'Never say "download now" — say "it\'s free" or "check yours"',
    'Pin a comment with the App Store link on every video',
  ] as const,
} as const;

// ---------------------------------------------------------------------------
// 6. PLATFORM CONTEXT — TikTok algorithm signals
// ---------------------------------------------------------------------------

export const PLATFORM_CONTEXT = {
  tiktok: {
    /**
     * Algorithm signals we optimize for — in priority order.
     */
    algorithmPriority: [
      { signal: 'Watch time / completion rate', weight: 'HIGHEST', tactic: 'Hook in 1s, tease payoff, deliver in middle, CTA at end' },
      { signal: 'Replay rate', weight: 'HIGH', tactic: 'Fast reveals that people watch again to catch the number' },
      { signal: 'Share rate', weight: 'HIGH', tactic: '"Tag a friend who collects X" or genuinely surprising prices' },
      { signal: 'Comment rate', weight: 'MEDIUM', tactic: 'Ask a question, leave a hot take, show something controversial' },
      { signal: 'Save rate', weight: 'MEDIUM', tactic: 'Educational content people bookmark — grading tips, price guides' },
      { signal: 'Profile visits', weight: 'MEDIUM', tactic: 'Series content ("Part 3 of scanning my entire collection")' },
    ] as const,

    /**
     * Posting strategy.
     */
    posting: {
      frequency: '1–2 videos per account per day (12 accounts = 12–24 videos/day)',
      bestTimes: ['7–9 AM local', '12–2 PM local', '7–10 PM local'],
      hashtagStrategy: [
        '3–5 niche tags (#pokemontcg #charizard #psa10)',
        '1–2 trend tags (check trending page)',
        '1 branded tag (#collectai)',
        'NEVER more than 8 total — dilutes reach',
      ],
      captionLength: '50–150 chars — hook + 1 line context + CTA',
      soundStrategy: 'Original sound builds creator identity. Trending sounds boost discovery but dilute brand.',
    },

    /**
     * Content patterns that work in collectibles niche (based on top performers).
     */
    winningPatterns: [
      { pattern: 'Price reveal with genuine reaction', why: 'Combines curiosity gap + authenticity + shareable moment' },
      { pattern: '"Found at X for $Y, actually worth $Z"', why: 'Treasure hunt narrative is universally compelling' },
      { pattern: 'Collection tier list / ranking', why: 'Drives comments (disagreement = engagement)' },
      { pattern: 'Grading prediction → actual result', why: 'Suspense + educational + rewatchable' },
      { pattern: '"If you own this, check now"', why: 'Direct relevance trigger — viewers check their own stuff' },
      { pattern: 'Before/after collection transformation', why: 'Progress porn — satisfying visual arc' },
      { pattern: '"3 cards worth more than you think"', why: 'List format + surprise = completion rate boost' },
    ] as const,
  },
} as const;

// ---------------------------------------------------------------------------
// 7. COMPETITIVE LANDSCAPE — know the battlefield
// ---------------------------------------------------------------------------

export const COMPETITIVE_LANDSCAPE = {
  directCompetitors: [
    {
      name: 'TCGPlayer',
      strength: 'Largest TCG marketplace, trusted pricing',
      weakness: 'TCG-only, no vision scan, no portfolio tracking, desktop-first',
      contentAngle: 'We search TCGPlayer + 36 other sources simultaneously',
    },
    {
      name: 'Cardmarket',
      strength: 'EU-dominant TCG marketplace',
      weakness: 'TCG-only, no mobile scan, no AI, EU-only',
      contentAngle: 'Works globally, all categories, AI-powered',
    },
    {
      name: 'Pricecharting.com',
      strength: 'Good for retro games and some cards',
      weakness: 'Website-only, manual search, limited categories, no scanning',
      contentAngle: 'Scan instead of search — 10x faster',
    },
    {
      name: 'Whatnot',
      strength: 'Live auction excitement, social selling',
      weakness: 'No price intelligence, no portfolio tracking, entertainment-first',
      contentAngle: 'Know what something is worth BEFORE you bid',
    },
  ] as const,

  indirectCompetitors: [
    {
      name: 'Spreadsheets / manual tracking',
      weakness: 'Tedious, prices go stale immediately, no scanning',
      contentAngle: '"I replaced my 200-row spreadsheet in 5 minutes"',
    },
    {
      name: 'eBay sold listings',
      weakness: 'Manual search per item, no aggregation, no alerts',
      contentAngle: 'We pull eBay + 36 others in one search',
    },
    {
      name: 'Reddit / Discord price checks',
      weakness: 'Slow, subjective, no historical data',
      contentAngle: '"Instead of posting and waiting 4 hours, I scanned it in 3 seconds"',
    },
  ] as const,
} as const;

// ---------------------------------------------------------------------------
// 8. CONTENT ANGLES — strategic themes for the learning loop
// ---------------------------------------------------------------------------

export const CONTENT_ANGLES = [
  {
    id: 'price_shock',
    name: 'Price Shock',
    description: 'Items worth way more (or less) than expected',
    emotionalTrigger: 'Surprise → curiosity → "what about mine?"',
    hookPatterns: [
      'This {item} is worth HOW MUCH?!',
      'I thought this was worth $X. I was wrong.',
      'The most expensive {niche} item ever sold',
    ],
    bestTemplates: ['whats_it_worth', 'pull_reveal'],
    exampleScript: 'Hook: "This card has been sitting in my binder for 15 years." → Scan → Price reveal: $4,200 → Reaction → "Scan yours — link in bio"',
  },
  {
    id: 'deal_hunting',
    name: 'Deal Hunting',
    description: 'Finding underpriced items and arbitrage opportunities',
    emotionalTrigger: 'Thrill of the hunt → FOMO → "I need to check too"',
    hookPatterns: [
      'I found this at {location} for ${low}. It\'s worth ${high}.',
      'The seller had NO idea what this was worth',
      'Best {niche} deal I\'ve ever found',
    ],
    bestTemplates: ['hidden_gem'],
    exampleScript: 'Hook: "Garage sale. $3 bin." → Show item → Scan → Reveal: $890 → "Thank you, CollectAI" → CTA',
  },
  {
    id: 'portfolio_flex',
    name: 'Portfolio Flex',
    description: 'Showing off collection value and growth over time',
    emotionalTrigger: 'Pride → validation → "I should track mine too"',
    hookPatterns: [
      'My {niche} collection is worth ${total}',
      '{X} months of collecting — here\'s what it\'s worth',
      'My top 5 most valuable items',
    ],
    bestTemplates: ['collection_flex'],
    exampleScript: 'Hook: "2 years. 340 items." → Open portfolio → Total: $47,820 → Scroll through top items → "What\'s yours worth?"',
  },
  {
    id: 'market_intelligence',
    name: 'Market Intelligence',
    description: 'Market movements, trends, vaulted items, price surges',
    emotionalTrigger: 'Urgency → FOMO → "I need to know this"',
    hookPatterns: [
      'If you own {item}, check your collection NOW',
      '{item} just got vaulted — prices are already moving',
      'This {niche} category is up {X}% this month',
    ],
    bestTemplates: ['market_alert'],
    exampleScript: 'Hook: "Funko just vaulted 12 figures." → List them → Show price charts → "Set up alerts so you never miss this — CollectAI"',
  },
  {
    id: 'ai_magic',
    name: 'AI Magic Moment',
    description: 'Demonstrating the scan/identification/grading tech',
    emotionalTrigger: 'Wonder → "that\'s actually useful" → trial intent',
    hookPatterns: [
      'I scanned my entire shelf in under a minute',
      'This app identified my card in 3 seconds',
      'AI graded my card — here\'s what PSA actually gave it',
    ],
    bestTemplates: ['whats_it_worth', 'pull_reveal'],
    exampleScript: 'Hook: "Can AI grade my card?" → Scan → AI says PSA 9 → Send to PSA → Result: PSA 9 → "Saved me $30" → CTA',
  },
  {
    id: 'education',
    name: 'Collector Education',
    description: 'Teaching what makes items valuable, how to spot fakes, grading tips',
    emotionalTrigger: 'Learning → confidence → trust in brand',
    hookPatterns: [
      '3 things that make a {item} valuable',
      'How to spot a fake {item} in 10 seconds',
      'Why your {item} isn\'t worth what you think',
    ],
    bestTemplates: ['whats_it_worth', 'market_alert'],
    exampleScript: 'Hook: "3 things that tank a card\'s value" → Show each with examples → "Check yours with CollectAI" → CTA',
  },
  {
    id: 'community',
    name: 'Community & Culture',
    description: 'Celebrating the collecting community, hot takes, debates',
    emotionalTrigger: 'Belonging → debate → comment engagement',
    hookPatterns: [
      'Hot take: {controversial opinion about niche}',
      'Rank these {niche} items worst to best',
      'The {niche} community needs to talk about this',
    ],
    bestTemplates: ['collection_flex', 'market_alert'],
    exampleScript: 'Hook: "Hot take: PSA is overrated." → Explain → Show CollectAI grading → "What do you think? Comment below"',
  },
] as const;

export type ContentAngleId = (typeof CONTENT_ANGLES)[number]['id'];
export type BrandVoiceTrait = (typeof BRAND_VOICE.personality.traits)[number];
