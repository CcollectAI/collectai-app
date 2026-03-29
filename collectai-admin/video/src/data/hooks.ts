// ═══════════════════════════════════════════════════════════════════════════
// CollectAI Video Hook Library — collector-native hooks per template
// ═══════════════════════════════════════════════════════════════════════════

export interface Hook {
  id: string;
  format: string;           // pull_reveal | whats_it_worth | hidden_gem | market_alert | collection_flex
  text: string;             // Hook text with {NICHE}, {ITEM}, {STAT} placeholders
  hookType: string;         // Maps to admin.config hookTypes
  retentionRate: number;    // 0-1 estimated performance
}

export const HOOKS: Hook[] = [
  // ─── Pull Reveal (Pack Opening / Grading Reveal) ───────────────────────
  {
    id: "pr-1",
    format: "pull_reveal",
    text: "This $3 pack had a ${STAT} card inside",
    hookType: "reveal",
    retentionRate: 0.52,
  },
  {
    id: "pr-2",
    format: "pull_reveal",
    text: "PSA just graded my childhood {NICHE} card...",
    hookType: "suspense",
    retentionRate: 0.48,
  },
  {
    id: "pr-3",
    format: "pull_reveal",
    text: "I didn't believe the AI grade until I saw this",
    hookType: "suspense",
    retentionRate: 0.46,
  },
  {
    id: "pr-4",
    format: "pull_reveal",
    text: "Opening the last pack. This is either $5 or $5,000.",
    hookType: "suspense",
    retentionRate: 0.54,
  },
  {
    id: "pr-5",
    format: "pull_reveal",
    text: "The rarest {NICHE} pull of my life just happened",
    hookType: "reveal",
    retentionRate: 0.50,
  },

  // ─── What's It Worth (Price Reveal / Valuation) ────────────────────────
  {
    id: "wiw-1",
    format: "whats_it_worth",
    text: "How much is this ACTUALLY worth?",
    hookType: "question",
    retentionRate: 0.49,
  },
  {
    id: "wiw-2",
    format: "whats_it_worth",
    text: "Everyone told me this was worth $50. They were wrong.",
    hookType: "hot-take",
    retentionRate: 0.47,
  },
  {
    id: "wiw-3",
    format: "whats_it_worth",
    text: "I scanned my entire {NICHE} collection. Total shocked me.",
    hookType: "reaction",
    retentionRate: 0.51,
  },
  {
    id: "wiw-4",
    format: "whats_it_worth",
    text: "You're pricing your {NICHE} wrong. Here's proof.",
    hookType: "hot-take",
    retentionRate: 0.44,
  },
  {
    id: "wiw-5",
    format: "whats_it_worth",
    text: "Is this {ITEM} worth what they're charging? Let's check.",
    hookType: "question",
    retentionRate: 0.43,
  },

  // ─── Hidden Gem (Thrift Find / The Hunt) ───────────────────────────────
  {
    id: "hg-1",
    format: "hidden_gem",
    text: "I found this at a garage sale for $2...",
    hookType: "reveal",
    retentionRate: 0.55,
  },
  {
    id: "hg-2",
    format: "hidden_gem",
    text: "$5 thrift store find. The app says it's worth...",
    hookType: "suspense",
    retentionRate: 0.53,
  },
  {
    id: "hg-3",
    format: "hidden_gem",
    text: "The seller had NO idea what they had",
    hookType: "reveal",
    retentionRate: 0.51,
  },
  {
    id: "hg-4",
    format: "hidden_gem",
    text: "Best {NICHE} find of 2026. I almost walked past it.",
    hookType: "suspense",
    retentionRate: 0.48,
  },

  // ─── Market Alert (Price Crash / Surge / Vault) ────────────────────────
  {
    id: "ma-1",
    format: "market_alert",
    text: "This just got VAULTED. Prices are already moving.",
    hookType: "reveal",
    retentionRate: 0.50,
  },
  {
    id: "ma-2",
    format: "market_alert",
    text: "If you own this, check your portfolio NOW",
    hookType: "challenge",
    retentionRate: 0.48,
  },
  {
    id: "ma-3",
    format: "market_alert",
    text: "The {NICHE} market just crashed. Here's why.",
    hookType: "hot-take",
    retentionRate: 0.46,
  },
  {
    id: "ma-4",
    format: "market_alert",
    text: "{ITEM} prices are up {STAT}% this week. What happened?",
    hookType: "question",
    retentionRate: 0.44,
  },
  {
    id: "ma-5",
    format: "market_alert",
    text: "New {NICHE} drop sells out in 3 minutes. Resale already 5x.",
    hookType: "reveal",
    retentionRate: 0.52,
  },

  // ─── Collection Flex (Showcase / Portfolio) ────────────────────────────
  {
    id: "cf-1",
    format: "collection_flex",
    text: "My ${STAT} collection in 15 seconds",
    hookType: "reveal",
    retentionRate: 0.47,
  },
  {
    id: "cf-2",
    format: "collection_flex",
    text: "3 years of collecting {NICHE}. Here's every piece.",
    hookType: "list",
    retentionRate: 0.45,
  },
  {
    id: "cf-3",
    format: "collection_flex",
    text: "The AI says my collection is worth HOW MUCH?",
    hookType: "reaction",
    retentionRate: 0.49,
  },
  {
    id: "cf-4",
    format: "collection_flex",
    text: "Rating my {NICHE} collection from worst to best",
    hookType: "list",
    retentionRate: 0.43,
  },
];

/** Get hooks for a specific template format, sorted by retention rate */
export function getHooksForFormat(format: string): Hook[] {
  return HOOKS
    .filter((h) => h.format === format)
    .sort((a, b) => b.retentionRate - a.retentionRate);
}

/** Get the single best hook for a format */
export function getBestHook(format: string): Hook | undefined {
  return getHooksForFormat(format)[0];
}

/** Replace placeholders in hook text */
export function renderHook(
  hook: Hook,
  vars: { niche?: string; item?: string; stat?: string },
): string {
  let text = hook.text;
  if (vars.niche) text = text.replace(/\{NICHE\}/g, vars.niche);
  if (vars.item) text = text.replace(/\{ITEM\}/g, vars.item);
  if (vars.stat) text = text.replace(/\{STAT\}/g, vars.stat);
  return text;
}
