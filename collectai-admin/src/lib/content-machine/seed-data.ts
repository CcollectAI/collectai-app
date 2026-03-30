// ---------------------------------------------------------------------------
// Content Machine — Seed data (local mirror of DB seeds for offline generation)
// ---------------------------------------------------------------------------

import type { ContentAccount, ContentPillar, ContentNiche, ContentProduct, ContentFormat, PresenceMode } from "./types";

// ─── Accounts ────────────────────────────────────────────────────────────

export const ACCOUNTS: ContentAccount[] = [
  {
    id: "acc-1",
    handle: "@collectai.app",
    displayName: "CollectAI",
    purpose: "Main brand — app features, market alerts, deals, conversion",
    platform: "tiktok",
    contentFocus: ["market-alert", "deal-hunting", "price-prediction", "app-feature"],
    isActive: true,
  },
  {
    id: "acc-2",
    handle: "@collectai.finds",
    displayName: "CollectAI Finds",
    purpose: "Thrift finds, hidden gems, deal hunting, unboxing, process",
    platform: "tiktok",
    contentFocus: ["deal-hunting", "unboxing-reveal", "grading-guide", "beginner-guide"],
    isActive: true,
  },
  {
    id: "acc-3",
    handle: "@collectai.grail",
    displayName: "CollectAI Grails",
    purpose: "Grail pieces, collection showcases, portfolio flex, rare items",
    platform: "tiktok",
    contentFocus: ["collection-showcase", "lifestyle-collector", "unboxing-reveal", "price-prediction"],
    isActive: true,
  },
];

// ─── Pillars ─────────────────────────────────────────────────────────────

export const PILLARS: ContentPillar[] = [
  {
    id: "pil-1", slug: "market-alert", name: "Market Alert",
    description: "Price movements, vaulted items, trending collectibles",
    targetMixPct: 20, defaultCta: "Download CollectAI to track prices",
    emoji: "🚨", bestFormats: ["reveal", "comparison", "POV"] as ContentFormat[],
    bestPresence: ["voiceover", "text_only"] as PresenceMode[], isActive: true,
  },
  {
    id: "pil-2", slug: "deal-hunting", name: "Deal Hunting",
    description: "Hidden gems, thrift finds, garage sale scores",
    targetMixPct: 15, defaultCta: "Scan any collectible with CollectAI",
    emoji: "💎", bestFormats: ["reveal", "unboxing", "POV"] as ContentFormat[],
    bestPresence: ["face", "voiceover", "hands_only"] as PresenceMode[], isActive: true,
  },
  {
    id: "pil-3", slug: "collection-showcase", name: "Collection Showcase",
    description: "Portfolio flex, shelf tours, collection milestones",
    targetMixPct: 15, defaultCta: "Track your collection in CollectAI",
    emoji: "👑", bestFormats: ["lifestyle", "reveal", "timelapse"] as ContentFormat[],
    bestPresence: ["face", "voiceover"] as PresenceMode[], isActive: true,
  },
  {
    id: "pil-4", slug: "grading-guide", name: "Grading Guide",
    description: "Condition assessment, authentication, grading tips",
    targetMixPct: 10, defaultCta: "Get AI condition grades with CollectAI",
    emoji: "🔍", bestFormats: ["tutorial", "comparison", "POV"] as ContentFormat[],
    bestPresence: ["hands_only", "voiceover"] as PresenceMode[], isActive: true,
  },
  {
    id: "pil-5", slug: "unboxing-reveal", name: "Unboxing & Reveal",
    description: "New pickups, mail day, pack openings",
    targetMixPct: 10, defaultCta: "See what it's worth — scan with CollectAI",
    emoji: "📦", bestFormats: ["unboxing", "reveal", "ASMR"] as ContentFormat[],
    bestPresence: ["hands_only", "face"] as PresenceMode[], isActive: true,
  },
  {
    id: "pil-6", slug: "price-prediction", name: "Price Prediction",
    description: "What's going up, what's crashing, investment tips",
    targetMixPct: 10, defaultCta: "CollectAI predicts prices with ML",
    emoji: "📈", bestFormats: ["comparison", "reveal", "tutorial"] as ContentFormat[],
    bestPresence: ["voiceover", "text_only"] as PresenceMode[], isActive: true,
  },
  {
    id: "pil-7", slug: "beginner-guide", name: "Beginner Guide",
    description: "How to start collecting, avoid fakes, first buys",
    targetMixPct: 10, defaultCta: "Start your collection with CollectAI",
    emoji: "🎓", bestFormats: ["tutorial", "comparison", "fix-it"] as ContentFormat[],
    bestPresence: ["face", "voiceover"] as PresenceMode[], isActive: true,
  },
  {
    id: "pil-8", slug: "lifestyle-collector", name: "Collector Lifestyle",
    description: "Desk setup, display shelves, collector routines",
    targetMixPct: 5, defaultCta: "Organize your collection in CollectAI",
    emoji: "🏠", bestFormats: ["lifestyle", "timelapse", "routine"] as ContentFormat[],
    bestPresence: ["face", "hands_only"] as PresenceMode[], isActive: true,
  },
  {
    id: "pil-9", slug: "app-feature", name: "App Feature",
    description: "CollectAI demos, QuickScan, portfolio analytics, new features",
    targetMixPct: 5, defaultCta: "Download CollectAI — link in bio",
    emoji: "📱", bestFormats: ["tutorial", "reveal", "transformation"] as ContentFormat[],
    bestPresence: ["voiceover", "hands_only"] as PresenceMode[], isActive: true,
  },
];

// ─── Niches ──────────────────────────────────────────────────────────────

export const NICHES: ContentNiche[] = [
  { id: "n-1", slug: "pokemon-tcg", name: "Pokemon TCG", categorySlug: "pokemon_tcg", emoji: "💠", priceRange: "$1 - $500K", audienceTags: ["gen-z", "nostalgia", "investors"], trendingTopics: ["Prismatic Evolutions", "PSA 10 chase", "alt art"], shortDescription: "Nostalgia meets investment", personalityTags: ["competitive", "nostalgic", "hype"] },
  { id: "n-2", slug: "mtg", name: "Magic: The Gathering", categorySlug: "mtg", emoji: "🪄", priceRange: "$1 - $100K", audienceTags: ["millennials", "competitive", "collectors"], trendingTopics: ["Reserved List", "Modern staples", "foil chase"], shortDescription: "The OG TCG", personalityTags: ["strategic", "patient", "knowledgeable"] },
  { id: "n-3", slug: "funko-pop", name: "Funko Pop", categorySlug: "funko", emoji: "👾", priceRange: "$5 - $15K", audienceTags: ["gen-z", "pop-culture", "casual"], trendingTopics: ["vaulted Pops", "SDCC exclusives", "grail hunt"], shortDescription: "Pop culture collectibles", personalityTags: ["fun", "hunting", "completionist"] },
  { id: "n-4", slug: "lego", name: "LEGO", categorySlug: "lego", emoji: "🧱", priceRange: "$10 - $10K", audienceTags: ["all-ages", "families", "investors"], trendingTopics: ["retiring sets", "GWP chase", "modular buildings"], shortDescription: "Sets that appreciate faster than stocks", personalityTags: ["patient", "detail-oriented", "builder"] },
  { id: "n-5", slug: "sneakers", name: "Sneakers", categorySlug: "sneakers", emoji: "👟", priceRange: "$50 - $50K", audienceTags: ["gen-z", "streetwear", "investors"], trendingTopics: ["Nike SB dunks", "Jordan retros", "Travis Scott"], shortDescription: "Hype-driven market", personalityTags: ["trendy", "fast-paced", "knowledgeable"] },
  { id: "n-6", slug: "watches", name: "Watches", categorySlug: "watches", emoji: "⌚", priceRange: "$100 - $500K", audienceTags: ["millennials", "luxury", "investors"], trendingTopics: ["Rolex waitlists", "Omega Swatch", "micro-brands"], shortDescription: "Horological treasures", personalityTags: ["patient", "refined", "knowledgeable"] },
  { id: "n-7", slug: "vinyl", name: "Vinyl Records", categorySlug: "vinyl", emoji: "🎵", priceRange: "$5 - $25K", audienceTags: ["millennials", "music-lovers", "crate-diggers"], trendingTopics: ["first pressings", "colored vinyl", "RSD drops"], shortDescription: "Analog warmth meets collector passion", personalityTags: ["passionate", "knowledgeable", "patient"] },
  { id: "n-8", slug: "warhammer", name: "Warhammer 40K", categorySlug: "warhammer", emoji: "⚔️", priceRange: "$10 - $5K", audienceTags: ["millennials", "hobbyists", "painters"], trendingTopics: ["OOP models", "Forge World", "pro-painted"], shortDescription: "Tabletop gaming meets fine art", personalityTags: ["creative", "patient", "detail-oriented"] },
  { id: "n-9", slug: "yugioh", name: "Yu-Gi-Oh!", categorySlug: "yugioh", emoji: "🃏", priceRange: "$1 - $100K", audienceTags: ["gen-z", "nostalgia", "competitive"], trendingTopics: ["Ghost Rares", "Starlight Rares", "QCSR"], shortDescription: "Ghost Rares driving massive value", personalityTags: ["competitive", "nostalgic", "sharp"] },
  { id: "n-10", slug: "kpop", name: "K-pop Merch", categorySlug: "kpop", emoji: "🎤", priceRange: "$5 - $5K", audienceTags: ["gen-z", "global", "completionist"], trendingTopics: ["photocards", "fansign exclusives", "season greetings"], shortDescription: "Photocard culture", personalityTags: ["passionate", "social", "completionist"] },
  { id: "n-11", slug: "hot-toys", name: "Hot Toys", categorySlug: "hot_toys", emoji: "🧸", priceRange: "$200 - $10K", audienceTags: ["millennials", "movie-fans", "display"], trendingTopics: ["Marvel exclusives", "Star Wars", "sold-out figures"], shortDescription: "Museum-quality sixth-scale figures", personalityTags: ["patient", "display-focused", "premium"] },
  { id: "n-12", slug: "manga", name: "Manga", categorySlug: "manga", emoji: "📚", priceRange: "$5 - $5K", audienceTags: ["gen-z", "anime-fans", "readers"], trendingTopics: ["OOP volumes", "box sets", "first editions"], shortDescription: "Out-of-print volumes driving demand", personalityTags: ["patient", "knowledgeable", "passionate"] },
];

// ─── Products ────────────────────────────────────────────────────────────

export const PRODUCTS: ContentProduct[] = [
  { id: "p-1", slug: "collectai-free", name: "CollectAI Free", category: "app", description: "Free tier — collection tracking, basic scanning", tier: "free", bestContentAngles: ["demo", "beginner", "comparison"] },
  { id: "p-2", slug: "collectai-pro", name: "CollectAI Pro", category: "subscription", description: "Pro tier — portfolio analytics, condition grading, set completion", tier: "pro", bestContentAngles: ["feature-demo", "before-after", "conversion"] },
  { id: "p-3", slug: "quickscan", name: "QuickScan", category: "feature", description: "AI-powered instant identification and valuation", tier: "free", bestContentAngles: ["reveal", "magic-moment", "demo"] },
  { id: "p-4", slug: "portfolio-analytics", name: "Portfolio Analytics", category: "feature", description: "Track portfolio value, ROI, condition distribution", tier: "pro", bestContentAngles: ["showcase", "data-reveal", "flex"] },
  { id: "p-5", slug: "deal-desk", name: "Deal Desk", category: "feature", description: "P2P marketplace with AI risk assessment", tier: "pro", bestContentAngles: ["deal-hunting", "trust", "demo"] },
  { id: "p-6", slug: "price-alerts", name: "Price Alerts", category: "feature", description: "Real-time notifications on price movements", tier: "free", bestContentAngles: ["urgency", "FOMO", "demo"] },
  { id: "p-7", slug: "condition-grading", name: "AI Condition Grading", category: "feature", description: "AI-powered condition assessment", tier: "pro", bestContentAngles: ["grading", "education", "comparison"] },
];

// ─── Pillar → Account mapping ────────────────────────────────────────────

export const ACCOUNT_BY_PILLAR: Record<string, string> = {
  "market-alert": "@collectai.app",
  "deal-hunting": "@collectai.finds",
  "collection-showcase": "@collectai.grail",
  "grading-guide": "@collectai.finds",
  "unboxing-reveal": "@collectai.finds",
  "price-prediction": "@collectai.app",
  "beginner-guide": "@collectai.finds",
  "lifestyle-collector": "@collectai.grail",
  "app-feature": "@collectai.app",
};

// ─── Pillar → Objective mapping ──────────────────────────────────────────

export const OBJECTIVE_BY_PILLAR: Record<string, import("./types").ObjectiveType[]> = {
  "market-alert": ["awareness", "retention"],
  "deal-hunting": ["awareness", "proof"],
  "collection-showcase": ["awareness", "retention"],
  "grading-guide": ["learning", "proof"],
  "unboxing-reveal": ["awareness", "proof"],
  "price-prediction": ["learning", "conversion"],
  "beginner-guide": ["learning", "awareness"],
  "lifestyle-collector": ["awareness", "retention"],
  "app-feature": ["conversion", "learning"],
};

// ─── Presence mode weights ───────────────────────────────────────────────

export const PRESENCE_WEIGHTS: Record<import("./types").PresenceMode, number> = {
  hands_only: 35,
  voiceover: 30,
  face: 25,
  text_only: 10,
};

// ─── Account weekly targets ──────────────────────────────────────────────

export const ACCOUNT_WEEKLY_TARGETS: Record<string, number> = {
  "@collectai.app": 5,
  "@collectai.finds": 4,
  "@collectai.grail": 3,
};

// ─── Weekly minimums per pillar ──────────────────────────────────────────

export const WEEKLY_MINIMUMS: Record<string, number> = {
  "market-alert": 2,
  "deal-hunting": 2,
  "collection-showcase": 2,
  "grading-guide": 1,
  "unboxing-reveal": 1,
  "price-prediction": 1,
  "beginner-guide": 1,
  "lifestyle-collector": 0,
  "app-feature": 0,
};

// ─── Posting times (EU prime time) ───────────────────────────────────────

export const POSTING_TIMES = ["07:00", "12:00", "18:00", "19:30", "21:00"];
