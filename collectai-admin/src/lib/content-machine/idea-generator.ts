// ---------------------------------------------------------------------------
// Content Machine — Idea Generator for CollectAI
// Generates structured content ideas with success-pattern fields
// ---------------------------------------------------------------------------

import type {
  ContentIdea,
  ContentFormat,
  PresenceMode,
  ObjectiveType,
  CommerceMode,
  GenerateIdeasOptions,
} from "./types";
import {
  PILLARS,
  NICHES,
  PRODUCTS,
  ACCOUNT_BY_PILLAR,
  OBJECTIVE_BY_PILLAR,
  PRESENCE_WEIGHTS,
} from "./seed-data";

// ─── Generation constants (extracted from magic numbers) ─────────────────

const NICHE_INCLUSION_RATE = 0.8;
const PRODUCT_INCLUSION_RATE = 0.5;
const COMMERCE_PILLAR_PRODUCT_RATE = 0.9;
const AFFILIATE_READY_RATE = 0.2;
const HOOK_DEDUP_ATTEMPTS = 8;
const COMMERCE_PILLARS = ["app-feature", "price-prediction"];
const BOOSTABLE_FORMATS: ContentFormat[] = ["reveal", "comparison", "unboxing", "POV"];
const BOOSTABLE_OBJECTIVES: ObjectiveType[] = ["awareness", "conversion"];
const SHORT_FORMAT_COMPLETION = 0.75;
const DEFAULT_COMPLETION = 0.7;
const LEARNING_SAVE_RATE = 0.08;
const DEFAULT_SAVE_RATE = 0.05;

// ─── Hook templates per pillar (15+ per pillar) ─────────────────────────

const HOOK_TEMPLATES: Record<string, string[]> = {
  "market-alert": [
    "This {NICHE} just got VAULTED. Prices are already moving.",
    "{NICHE} prices crashed 40% overnight. Here's why.",
    "This {ITEM} was $50 last month. Now it's ${PRICE}.",
    "Everyone is panic selling {NICHE}. Smart money is buying.",
    "The {NICHE} market just flipped. Nobody is talking about this.",
    "This {NICHE} hit an all-time high today. Did you catch it?",
    "3 {NICHE} items about to spike. Set your alerts NOW.",
    "I predicted this {NICHE} crash 2 weeks ago. Here's what's next.",
    "This discontinued {ITEM} just tripled in value.",
    "The {NICHE} bubble is bursting. Or is it?",
    "Breaking: {ITEM} just got a reprint announcement. RIP to holders.",
    "{NICHE} supply just dried up. Check these prices.",
    "This {NICHE} item went from $20 to ${PRICE} in one week.",
    "Market update: {NICHE} is the most volatile niche right now.",
    "If you're holding {ITEM}, you need to see this price chart.",
    "The {NICHE} crash everyone predicted? It's actually happening.",
  ],
  "deal-hunting": [
    "$5 thrift store find. The app says it's worth ${PRICE}.",
    "I found this {ITEM} for $3 at a garage sale. You won't believe the value.",
    "The best {NICHE} deal I've ever found. Under ${PRICE}.",
    "How I find {NICHE} deals that nobody else sees.",
    "This {NICHE} was hiding in a $1 bin. It's worth ${PRICE}.",
    "I just sniped this {ITEM} for 90% below market. Here's how.",
    "Garage sale haul: everything here for $20. Real value? ${PRICE}.",
    "The one trick that finds me {NICHE} deals every single week.",
    "Scanning thrift store finds with AI. This one broke the app.",
    "Found a {ITEM} at Goodwill. The AI valuation shocked me.",
    "Estate sale score: this {ITEM} was buried under junk.",
    "The seller had NO idea what this {NICHE} item was worth.",
    "Facebook Marketplace deal: {ITEM} listed for $10. Worth ${PRICE}.",
    "My best {NICHE} flip this month. Buy price vs sell price.",
    "How to negotiate {NICHE} prices at flea markets. My script.",
    "This {NICHE} lot was listed as 'junk'. One piece was worth ${PRICE}.",
  ],
  "collection-showcase": [
    "My entire {NICHE} collection in 60 seconds.",
    "The AI says my collection is worth HOW MUCH?",
    "Building a {NICHE} collection from $0 to ${PRICE}.",
    "Every grail in my {NICHE} collection. Years in the making.",
    "Portfolio check: my {NICHE} collection value this month.",
    "I started collecting {NICHE} 3 years ago. Here's every piece.",
    "Top 5 most valuable items in my {NICHE} collection.",
    "One shelf. ${PRICE} worth of {NICHE}. Tour time.",
    "The piece that started my {NICHE} collection.",
    "Rating my own {NICHE} collection — brutally honest.",
    "Collection update: what I added and what I sold this month.",
    "Reorganizing my {NICHE} display. Before and after.",
    "The one {NICHE} piece I would never sell. Even for ${PRICE}.",
    "My collection hit a new milestone. Here's the portfolio breakdown.",
    "Roast my {NICHE} collection. Be honest.",
    "Every {NICHE} piece ranked from worst to best purchase.",
  ],
  "grading-guide": [
    "Is this {ITEM} a PSA 10? Let's check with AI.",
    "Mint vs Near Mint: the difference is worth ${PRICE}.",
    "3 signs your {NICHE} item is fake. #2 is subtle.",
    "I grade this {ITEM} condition live — you guess first.",
    "This tiny scratch just cost me ${PRICE} in value.",
    "AI grading vs PSA: how close can it get?",
    "The most common {NICHE} grading mistake beginners make.",
    "How to spot a fake {ITEM} in 10 seconds.",
    "Before and after: what proper storage does to value.",
    "This centering issue dropped the grade by 2 points.",
    "Stop making this {NICHE} storage mistake. It's destroying value.",
    "The whitening test: real vs fake {NICHE} side by side.",
    "I sent this to PSA. Predicted grade vs actual grade.",
    "Edge wear that most collectors miss. Check your {NICHE}.",
    "This {ITEM} looks mint. But zoom in on this corner...",
    "Pack-fresh doesn't always mean PSA 10. Here's why.",
  ],
  "unboxing-reveal": [
    "Opening the last pack. This is either $5 or ${PRICE}.",
    "Mail day! Let's see what {NICHE} arrived today.",
    "{NICHE} mystery box unboxing. Was it worth ${PRICE}?",
    "I can't believe what was in this {NICHE} package.",
    "Unboxing ${PRICE} worth of {NICHE}. Biggest haul yet.",
    "The rarest {NICHE} pull of my life just happened.",
    "This sealed {ITEM} has been waiting 10 years to be opened.",
    "Blind box opening — the odds of hitting are 1 in 50.",
    "My most expensive {NICHE} purchase ever. Was it worth it?",
    "POV: opening a vintage {NICHE} pack for the first time.",
    "The packaging on this {ITEM} is insane. Let me show you.",
    "Someone sent me a mystery {NICHE} box. I have zero clue what's inside.",
    "Ripping packs until I hit {ITEM}. This could take a while.",
    "I ordered the wrong {NICHE} item. Or did I?",
    "Double-boxed, double-sleeved, and still arrived damaged. Or so I thought.",
    "Last booster box of {ITEM} I could find. Let's see if it was worth it.",
  ],
  "price-prediction": [
    "5 {NICHE} items I think will double by December.",
    "Everyone is buying {ITEM}. I think it's a trap.",
    "This {NICHE} pattern predicts the next price spike.",
    "Why I'm going all-in on {NICHE} right now.",
    "The ML model says this {ITEM} will be worth ${PRICE} next year.",
    "{NICHE} that everyone ignores but will moon in 2027.",
    "Comparing {NICHE} prices: 2024 vs 2026. The trend is clear.",
    "I asked AI to predict {NICHE} prices. The results surprised me.",
    "Buy these 3 {NICHE} items before everyone else catches on.",
    "The {NICHE} market cycle: where are we now?",
    "This {ITEM} is at the bottom. Here's why I'm buying.",
    "Historical data says {NICHE} peaks every Q4. Here's the pattern.",
    "The AI confidence score on this {NICHE} prediction is 94%.",
    "Hold or sell? What the data says about {ITEM} right now.",
    "3 overpriced {NICHE} items to avoid. The data is clear.",
    "{NICHE} sleeper picks that the algorithm flagged this week.",
  ],
  "beginner-guide": [
    "You just started collecting {NICHE}? Watch this first.",
    "The 5 biggest mistakes new {NICHE} collectors make.",
    "How to start a {NICHE} collection with just $50.",
    "I wish someone told me this before I started collecting {NICHE}.",
    "{NICHE} collecting 101: everything you need to know.",
    "The one tool every {NICHE} collector needs. (It's free.)",
    "Don't buy {NICHE} until you know these 3 things.",
    "Beginner vs Pro {NICHE} collection — what changed?",
    "How I built my {NICHE} knowledge from zero.",
    "First {NICHE} purchase guide: what actually holds value.",
    "New to {NICHE}? Here's the $50 starter kit I'd recommend.",
    "The {NICHE} rabbit hole: where to start without getting overwhelmed.",
    "Red flags when buying {NICHE} online. Protect yourself.",
    "Your first {NICHE} will probably be a mistake. Here's why that's okay.",
    "How to learn {NICHE} values fast. My exact process.",
    "Stop buying random {NICHE}. Build a focused collection instead.",
  ],
  "lifestyle-collector": [
    "The perfect {NICHE} display setup. Took me 3 days.",
    "Day in the life of a {NICHE} collector.",
    "How I organize ${PRICE} worth of collectibles.",
    "The collector desk setup tour you've been waiting for.",
    "Saturday morning: coffee, shelving, and {NICHE}.",
    "Building the ultimate display wall for my collection.",
    "The collector routine that keeps my hobby organized.",
    "Turning a spare room into a {NICHE} museum.",
    "The lighting setup that makes your {NICHE} display look gallery-level.",
    "IKEA hacks for displaying your {NICHE} collection.",
    "My collector morning routine. It's surprisingly calming.",
    "The {NICHE} collection room tour nobody asked for. But here it is.",
    "Cleaning and organizing day. My {NICHE} shelves needed this.",
    "How I protect my {NICHE} from dust, UV, and humidity.",
    "The display case that changed how I show my collection.",
  ],
  "app-feature": [
    "I scanned a random {ITEM} and the AI knew everything about it.",
    "This app tracks your collection value in real time.",
    "POV: you find a {ITEM} and need to know the price NOW.",
    "How I manage a ${PRICE} collection from my phone.",
    "The app that tells you if a deal is actually good.",
    "I let AI grade my {NICHE} collection. The results were brutal.",
    "New feature: price alerts just got smarter.",
    "From shoebox to organized: digitizing my {NICHE} collection.",
    "Watch me scan 10 items in 60 seconds. The AI is fast.",
    "My portfolio went up 12% this month. Here's the breakdown.",
    "The feature that finds duplicate items in your collection.",
    "Set a price alert and forget. The app notifies you when it hits.",
    "Quick demo: scanning, grading, and valuing a {ITEM} in under 30 seconds.",
    "My collection insurance needs this. Export your entire portfolio.",
    "Condition grading without sending it to PSA? The AI does it live.",
  ],
};

// ─── Format mapping by objective ─────────────────────────────────────────

const FORMAT_BY_OBJECTIVE: Record<ObjectiveType, ContentFormat[]> = {
  awareness: ["reveal", "POV", "comparison", "top-list"],
  proof: ["unboxing", "reveal", "comparison", "tutorial"],
  learning: ["tutorial", "comparison", "fix-it", "top-list"],
  conversion: ["reveal", "transformation", "tutorial", "comparison"],
  retention: ["lifestyle", "routine", "timelapse", "ASMR"],
};

// ─── Duration by format ──────────────────────────────────────────────────

const DURATION_BY_FORMAT: Record<ContentFormat, string> = {
  tutorial: "60-180s",
  timelapse: "15-45s",
  POV: "15-30s",
  unboxing: "30-90s",
  ASMR: "30-60s",
  routine: "30-60s",
  reveal: "15-30s",
  comparison: "30-90s",
  transformation: "15-45s",
  "fix-it": "30-60s",
  lifestyle: "15-45s",
  "top-list": "30-90s",
};

// ─── Niche-specific hashtags ─────────────────────────────────────────────

const NICHE_HASHTAGS: Record<string, string[]> = {
  "pokemon-tcg": ["#PokemonTCG", "#Pokemon", "#PokemonCards", "#TCG", "#CardPull"],
  mtg: ["#MTG", "#MagicTheGathering", "#MTGCommunity", "#TCG"],
  "funko-pop": ["#FunkoPop", "#Funko", "#FunkoCollector", "#PopVinyl"],
  lego: ["#LEGO", "#LEGOCollector", "#LEGOInvesting", "#AFOL"],
  sneakers: ["#Sneakers", "#SneakerHead", "#Kicks", "#SneakerCollection"],
  watches: ["#Watches", "#WatchCollector", "#Horology", "#LuxuryWatches"],
  vinyl: ["#Vinyl", "#VinylRecords", "#VinylCollector", "#RecordCollection"],
  warhammer: ["#Warhammer", "#Warhammer40K", "#MiniPainting", "#TabletopGaming"],
  yugioh: ["#YuGiOh", "#YuGiOhTCG", "#YuGiOhCards", "#TCG"],
  kpop: ["#Kpop", "#KpopPhotocard", "#KpopCollection", "#Photocard"],
  "hot-toys": ["#HotToys", "#SixthScale", "#ActionFigures", "#Collectibles"],
  manga: ["#Manga", "#MangaCollection", "#MangaCollector", "#Anime"],
};

// ─── Niche-aware price ranges for realistic interpolation ────────────────

const NICHE_PRICES: Record<string, string[]> = {
  "pokemon-tcg": ["200", "500", "1,500", "5,000", "25,000"],
  mtg: ["100", "500", "2,000", "10,000", "50,000"],
  "funko-pop": ["50", "200", "500", "2,000", "8,000"],
  lego: ["100", "300", "800", "2,000", "5,000"],
  sneakers: ["200", "500", "1,500", "5,000", "20,000"],
  watches: ["500", "2,000", "10,000", "50,000", "200,000"],
  vinyl: ["50", "200", "500", "2,000", "10,000"],
  warhammer: ["50", "200", "500", "1,500", "3,000"],
  yugioh: ["100", "500", "2,000", "10,000", "50,000"],
  kpop: ["50", "200", "500", "1,500", "3,000"],
  "hot-toys": ["300", "800", "1,500", "3,000", "8,000"],
  manga: ["50", "200", "500", "1,500", "3,000"],
};

const DEFAULT_PRICES = ["50", "200", "500", "1,000", "2,500", "5,000", "10,000"];

// ─── Boostable reason templates ──────────────────────────────────────────

const BOOSTABLE_REASONS: string[] = [
  "Strong hook + visible product + native pacing — good for Spark Ads",
  "High scroll-stop potential + clear CTA — boostable format",
  "Curiosity gap + product demo moment — paid amplification friendly",
  "Immediate hook + readable without sound — performs well as paid creative",
  "Visual reveal + emotional payoff — high share potential for paid reach",
];

// ─── Utility helpers ─────────────────────────────────────────────────────

function weightedRandom<T extends string>(weights: Record<T, number>): T {
  const entries = Object.entries(weights) as [T, number][];
  const total = entries.reduce((s, [, w]) => s + w, 0);
  let r = Math.random() * total;
  for (const [key, weight] of entries) {
    r -= weight;
    if (r <= 0) return key;
  }
  return entries[entries.length - 1][0];
}

function pickRandom<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function uid(): string {
  return `idea-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function interpolateHook(template: string, niche: (typeof NICHES)[number]): string {
  const item = pickRandom(niche.trendingTopics);
  const prices = NICHE_PRICES[niche.slug] ?? DEFAULT_PRICES;
  const price = pickRandom(prices);
  return template
    .replace(/\{NICHE\}/g, niche.name)
    .replace(/\{ITEM\}/g, item)
    .replace(/\{PRICE\}/g, price);
}

function assessBoostable(idea: Partial<ContentIdea>): { paidCandidate: boolean; boostableReason: string | undefined } {
  const isBoostable =
    BOOSTABLE_FORMATS.includes(idea.format as ContentFormat) &&
    idea.presenceMode !== "text_only" &&
    BOOSTABLE_OBJECTIVES.includes(idea.objectiveType as ObjectiveType);

  return {
    paidCandidate: isBoostable,
    boostableReason: isBoostable ? pickRandom(BOOSTABLE_REASONS) : undefined,
  };
}

// ─── Main generator ──────────────────────────────────────────────────────

export function generateIdeas(opts: GenerateIdeasOptions = {}): ContentIdea[] {
  const count = Math.min(Math.max(opts.count ?? 30, 1), 100);
  const lang = opts.languageCode ?? "en";
  const usedHooks = new Set<string>();
  const ideas: ContentIdea[] = [];

  const activePillars = PILLARS.filter((p) => {
    if (opts.pillarFilter?.length) return opts.pillarFilter.includes(p.slug);
    return p.isActive;
  });
  if (activePillars.length === 0) return ideas;

  const pillarWeights: Record<string, number> = {};
  for (const p of activePillars) pillarWeights[p.slug] = p.targetMixPct;

  const activeNiches = NICHES.filter((n) => {
    if (opts.nicheFilter?.length) return opts.nicheFilter.includes(n.slug);
    return true;
  });
  if (activeNiches.length === 0) return ideas;

  for (let i = 0; i < count; i++) {
    // 1. Pick pillar
    const pillarSlug = weightedRandom(pillarWeights);
    const pillar = activePillars.find((p) => p.slug === pillarSlug)!;

    // 2. Pick account
    let accountHandle = ACCOUNT_BY_PILLAR[pillarSlug] ?? "@collectai.app";
    if (opts.accountFilter?.length && !opts.accountFilter.includes(accountHandle)) {
      accountHandle = pickRandom(opts.accountFilter);
    }

    // 3. Pick niche + product with configurable rates
    const includeNiche = Math.random() < NICHE_INCLUSION_RATE;
    const niche = includeNiche ? pickRandom(activeNiches) : undefined;

    const isCommercePillar = COMMERCE_PILLARS.includes(pillarSlug);
    const includeProduct = Math.random() < (isCommercePillar ? COMMERCE_PILLAR_PRODUCT_RATE : PRODUCT_INCLUSION_RATE);
    const product = includeProduct ? pickRandom(PRODUCTS) : undefined;

    // 4. Pick objective, format, presence
    const objectives = OBJECTIVE_BY_PILLAR[pillarSlug] ?? ["awareness"];
    const objective = pickRandom(objectives);
    const formatOptions = FORMAT_BY_OBJECTIVE[objective].filter((f) =>
      pillar.bestFormats.includes(f)
    );
    const format: ContentFormat = formatOptions.length > 0 ? pickRandom(formatOptions) : pickRandom(pillar.bestFormats);

    const presenceMode: PresenceMode = pillar.bestPresence.length > 0
      ? pickRandom(pillar.bestPresence)
      : weightedRandom(PRESENCE_WEIGHTS);

    // 5. Generate hook (with deduplication)
    const templates = HOOK_TEMPLATES[pillarSlug] ?? HOOK_TEMPLATES["market-alert"];
    let hook = "";
    const hookNiche = niche ?? pickRandom(NICHES);
    for (let attempt = 0; attempt < HOOK_DEDUP_ATTEMPTS; attempt++) {
      const candidate = interpolateHook(pickRandom(templates), hookNiche);
      if (!usedHooks.has(candidate)) {
        hook = candidate;
        usedHooks.add(candidate);
        break;
      }
    }
    if (!hook) hook = interpolateHook(pickRandom(templates), hookNiche);

    // 6. Commerce mode
    const commerceMode: CommerceMode = isCommercePillar
      ? "organic_plus_commerce"
      : Math.random() < AFFILIATE_READY_RATE
        ? "affiliate_ready"
        : "organic";

    // 7. Assess boostable
    const { paidCandidate, boostableReason } = assessBoostable({
      format,
      presenceMode,
      objectiveType: objective,
    });

    // 8. Build idea
    const title = `${pillar.emoji} ${hook.slice(0, 60)}${hook.length > 60 ? "..." : ""}`;

    const shotList = buildShotList(format, presenceMode, niche, product);
    const voiceover = buildVoiceover(hook, pillar, niche, product);
    const concept = buildConcept(pillar, niche, product, objective);

    const nicheHashtags = niche ? (NICHE_HASHTAGS[niche.slug] ?? []) : [];
    const hashtags = [
      "#CollectAI",
      "#Collectibles",
      ...nicheHashtags.slice(0, 3),
      "#CollectorsOfTikTok",
    ].slice(0, 6);

    const targetKeyword = niche
      ? `${niche.name} ${pillar.name.toLowerCase()}`
      : `collectibles ${pillar.name.toLowerCase()}`;

    const isShortFormat = format === "reveal" || format === "POV";

    ideas.push({
      id: uid(),
      title,
      hook,
      concept,
      shotList,
      voiceover,
      cta: pillar.defaultCta,

      pillarSlug,
      pillarName: pillar.name,
      pillarEmoji: pillar.emoji,
      accountHandle,
      productSlug: product?.slug,
      productName: product?.name,
      nicheSlug: niche?.slug,
      nicheName: niche?.name,
      nicheEmoji: niche?.emoji,

      objectiveType: objective,
      commerceMode,
      presenceMode,
      paidCandidate,
      affiliateReady: commerceMode === "affiliate_ready",
      boostableReason,

      targetKeyword,
      hashtags,

      format,
      estimatedDuration: DURATION_BY_FORMAT[format],
      languageCode: lang,

      status: "draft",
      priority: paidCandidate ? "high" : "normal",

      targetCompletionRate: isShortFormat ? SHORT_FORMAT_COMPLETION : DEFAULT_COMPLETION,
      targetSaveRate: objective === "learning" ? LEARNING_SAVE_RATE : DEFAULT_SAVE_RATE,
    });
  }

  return ideas;
}

// ─── Shot list builder ───────────────────────────────────────────────────

function buildShotList(
  format: ContentFormat,
  presence: PresenceMode,
  niche?: (typeof NICHES)[number],
  product?: (typeof PRODUCTS)[number]
): string[] {
  const nicheLabel = niche?.name ?? "collectible";
  const productLabel = product?.name ?? "CollectAI";

  const shots: Record<ContentFormat, string[]> = {
    reveal: [
      `Open on ${nicheLabel} item — blurred or hidden`,
      "Build suspense with close-up details",
      "Reveal moment — full item or price shown",
      `CTA overlay: mention ${productLabel}`,
    ],
    tutorial: [
      `Introduce the topic — ${nicheLabel} context`,
      "Step-by-step walkthrough with close-ups",
      "Show common mistakes / pitfalls",
      "Final result / summary",
      `CTA: ${productLabel} demo or download prompt`,
    ],
    unboxing: [
      "Show sealed package — build anticipation",
      "Hands opening the package",
      `Reveal each ${nicheLabel} item slowly`,
      "React to items — highlight best piece",
      "Scan with CollectAI for instant valuation",
    ],
    comparison: [
      "Side-by-side setup of items being compared",
      "Detail shots: condition, features, packaging",
      "Price/value comparison overlay",
      "Winner declaration with reasoning",
    ],
    POV: [
      `POV text: "${nicheLabel}-related scenario"`,
      "Quick reaction shots or item reveals",
      "Punchy ending — surprise or payoff",
    ],
    timelapse: [
      "Wide establishing shot of setup",
      `Time-lapse of ${nicheLabel} process`,
      "Final reveal of completed result",
    ],
    ASMR: [
      `Close-up of ${nicheLabel} item — focus on texture`,
      "Slow, deliberate handling — no talking",
      "Page turns / clicks / packaging sounds",
      "Final beauty shot",
    ],
    transformation: [
      "Before state — raw / uncleaned / ungraded",
      "Process of improvement / organization",
      "After state — dramatic improvement shown",
    ],
    "fix-it": [
      "Show the problem clearly",
      "Explain the fix step by step",
      "Before/after comparison",
    ],
    lifestyle: [
      `${nicheLabel} items in everyday context`,
      `${presence === "face" ? "Founder" : "Hands"} interacting naturally`,
      "Aesthetic B-roll of display / desk / shelf",
    ],
    routine: [
      "Morning or evening routine establishing shot",
      `Interaction with ${nicheLabel} items`,
      "Calm, satisfying close-up moments",
      "End with organized / aesthetic result",
    ],
    "top-list": [
      "Title card: top N list topic",
      "Quick cuts through each ranked item",
      "#1 reveal with extra detail",
      "CTA: what would YOUR #1 be?",
    ],
  };

  return shots[format] ?? shots.reveal;
}

// ─── Voiceover builder ───────────────────────────────────────────────────

const VOICEOVER_OUTROS: Record<ObjectiveType, string[]> = {
  awareness: [
    "Follow for more content like this.",
    "Save this — you'll want to come back to it.",
    "What do you think? Drop a comment.",
  ],
  proof: [
    "The numbers don't lie. Link in bio.",
    "See it for yourself — CollectAI, link in bio.",
    "Real results. No cap.",
  ],
  learning: [
    "Save this for later.",
    "Share this with someone who needs to see it.",
    "Part 2 coming soon — follow so you don't miss it.",
  ],
  conversion: [
    "CollectAI — free download, link in bio.",
    "Try it yourself. Link in bio.",
    "Download CollectAI and see what your collection is really worth.",
  ],
  retention: [
    "Follow for the journey.",
    "More collection content coming.",
    "What's your routine? Comment below.",
  ],
};

function buildVoiceover(
  hook: string,
  pillar: (typeof PILLARS)[number],
  niche?: (typeof NICHES)[number],
  product?: (typeof PRODUCTS)[number],
): string {
  const nicheLabel = niche?.name ?? "collectibles";
  const objective = OBJECTIVE_BY_PILLAR[pillar.slug]?.[0] ?? "awareness";
  const outros = VOICEOVER_OUTROS[objective] ?? VOICEOVER_OUTROS.awareness;

  const middle = product
    ? `${pillar.description}. ${product.name} makes this easy.`
    : `${pillar.description} for ${nicheLabel}.`;

  return `${hook} [pause] ${middle} [pause] ${pickRandom(outros)}`;
}

// ─── Concept builder ─────────────────────────────────────────────────────

function buildConcept(
  pillar: (typeof PILLARS)[number],
  niche?: (typeof NICHES)[number],
  product?: (typeof PRODUCTS)[number],
  objective?: ObjectiveType
): string {
  const nicheLabel = niche?.name ?? "collectibles";
  const productLabel = product?.name ?? "the app";

  const concepts: Record<ObjectiveType, string[]> = {
    awareness: [
      `Spotlight on ${nicheLabel} — hook with a surprising price or trend, then reveal.`,
      `Quick-hit ${nicheLabel} content designed to stop the scroll and introduce ${productLabel}.`,
      `Curiosity-driven ${nicheLabel} content that makes viewers want to learn more.`,
    ],
    proof: [
      `Real results using ${productLabel} on a ${nicheLabel} item — show the scan, grade, or valuation live.`,
      `Demonstrating value through a real ${nicheLabel} find or acquisition.`,
      `Social proof: what actual ${nicheLabel} collectors achieve with ${productLabel}.`,
    ],
    learning: [
      `Educational ${nicheLabel} content: teach something actionable the viewer can use today.`,
      `Break down a ${nicheLabel} concept that most beginners get wrong.`,
      `Data-driven ${nicheLabel} insight that changes how collectors think about value.`,
    ],
    conversion: [
      `Show ${productLabel} solving a real ${nicheLabel} collector problem — make the value obvious.`,
      `Direct path from ${nicheLabel} pain point to ${productLabel} solution.`,
      `Feature highlight: ${productLabel} demo with a ${nicheLabel} item that proves the point.`,
    ],
    retention: [
      `Lifestyle content that makes ${nicheLabel} collecting feel aspirational and organized.`,
      `Satisfying ${nicheLabel} content that keeps existing followers engaged and saving.`,
      `Community-building ${nicheLabel} content: invite engagement and discussion.`,
    ],
  };

  return pickRandom(concepts[objective ?? "awareness"]);
}

// ─── Series generator ────────────────────────────────────────────────────

export function generateSeries(
  pillarSlug: string,
  nicheSlug: string,
  count: number = 5
): ContentIdea[] {
  const seriesId = `series-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  const ideas = generateIdeas({
    count: Math.min(count, 10),
    pillarFilter: [pillarSlug],
    nicheFilter: [nicheSlug],
  });

  return ideas.map((idea, i) => ({
    ...idea,
    seriesId,
    seriesOrder: i + 1,
    title: `${idea.pillarEmoji} Part ${i + 1}: ${idea.hook.slice(0, 50)}...`,
  }));
}
