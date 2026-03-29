// ---------------------------------------------------------------------------
// Video Generator — data layer for Remotion video pipeline integration
// Connects to existing UGC pods, swipe file hooks, and learning system
// ---------------------------------------------------------------------------

import { getSupabase, isSupabaseConfigured } from "@/lib/supabase";

// ─── Types ──────────────────────────────────────────────────────────────

export type TemplateId = "pull-reveal" | "whats-it-worth" | "hidden-gem" | "market-alert" | "collection-flex";

export interface VideoTemplate {
  id: TemplateId;
  compositionId: string;
  label: string;
  description: string;
  bestFor: string;
  avgDuration: string;
  icon: string;
}

export interface VideoScript {
  id: string;
  templateId: TemplateId;
  compositionId: string;
  nicheId: string;
  nicheLabel: string;
  language: string;
  hookText: string;
  hookId: string;
  props: Record<string, unknown>;
  createdAt: string;
  status: "draft" | "rendering" | "rendered" | "posted" | "tracking";
  estimatedCost: number;
  renderId?: string;
  renderUrl?: string;
  videoUrl?: string;
  // Performance
  views?: number;
  retention3s?: number;
  classification?: "hit" | "average" | "fail" | "pending";
  // A/B testing
  abGroup?: "A" | "B";
  abPairId?: string;
  abWinner?: boolean;
}

export interface VideoQueueStats {
  totalScripts: number;
  byStatus: Record<string, number>;
  estimatedCostTotal: number;
  nicheBreakdown: { nicheId: string; nicheLabel: string; count: number }[];
  templateBreakdown: { templateId: string; label: string; count: number }[];
}

export interface AutomationRule {
  id: string;
  name: string;
  description: string;
  trigger: string;
  action: string;
  isActive: boolean;
  lastTriggered?: string;
  timesTriggered: number;
}

// ─── Templates ───────────────────────────────────────────────────────────

export const TEMPLATES: VideoTemplate[] = [
  {
    id: "pull-reveal",
    compositionId: "PullReveal",
    label: "Pull Reveal",
    description: "Pack opening / grading reveal — suspense + dopamine hit",
    bestFor: "TCGs (Pokemon, MTG, Yu-Gi-Oh), blind boxes, sealed product",
    avgDuration: "15s",
    icon: "\u{1F3B0}",
  },
  {
    id: "whats-it-worth",
    compositionId: "WhatsItWorth",
    label: "What's It Worth?",
    description: "Curiosity gap price reveal — ties to QuickScan feature",
    bestFor: "Any niche — universal curiosity about value",
    avgDuration: "18s",
    icon: "\u{1F4B0}",
  },
  {
    id: "hidden-gem",
    compositionId: "HiddenGem",
    label: "Hidden Gem",
    description: "Thrift find / garage sale hunt — aspiration + FOMO",
    bestFor: "LEGO, vinyl, vintage toys, watches, retro games",
    avgDuration: "18s",
    icon: "\u{1F48E}",
  },
  {
    id: "market-alert",
    compositionId: "MarketAlert",
    label: "Market Alert",
    description: "Price crash / surge / vault — urgency-driven FOMO",
    bestFor: "Vaulted items, new drops, market movements",
    avgDuration: "16s",
    icon: "\u{1F6A8}",
  },
  {
    id: "collection-flex",
    compositionId: "CollectionFlex",
    label: "Collection Flex",
    description: "Portfolio showcase — social proof + aspiration",
    bestFor: "High-value collections, portfolio tracking feature",
    avgDuration: "20s",
    icon: "\u{1F451}",
  },
];

export const NICHE_OPTIONS = [
  { id: "pokemon", label: "Pokemon TCG", emoji: "\u{1F4A0}", podId: "pokemon", color: "#FFD700" },
  { id: "mtg", label: "Magic: The Gathering", emoji: "\u{1FA84}", podId: "mtg", color: "#8B5CF6" },
  { id: "funko", label: "Funko Pop", emoji: "\u{1F47E}", podId: "funko", color: "#EC4899" },
  { id: "warhammer", label: "Warhammer 40K", emoji: "\u{2694}\u{FE0F}", podId: "warhammer", color: "#EF4444" },
  { id: "sneakers", label: "Sneakers", emoji: "\u{1F45F}", podId: "sneakers", color: "#3B82F6" },
  { id: "watches", label: "Watches", emoji: "\u{231A}", podId: "watches", color: "#14B8A6" },
  { id: "vinyl", label: "Vinyl Records", emoji: "\u{1F3B5}", podId: "vinyl", color: "#F97316" },
  { id: "lego", label: "LEGO", emoji: "\u{1F9F1}", podId: "general", color: "#81D8D0" },
  { id: "hot_toys", label: "Hot Toys", emoji: "\u{1F9F8}", podId: "general", color: "#81D8D0" },
  { id: "yugioh", label: "Yu-Gi-Oh!", emoji: "\u{1F0CF}", podId: "general", color: "#81D8D0" },
  { id: "kpop", label: "K-pop Merch", emoji: "\u{1F3A4}", podId: "general", color: "#81D8D0" },
  { id: "manga", label: "Manga", emoji: "\u{1F4DA}", podId: "general", color: "#81D8D0" },
];

// ─── Demo Data ───────────────────────────────────────────────────────────

function getDemoScripts(): VideoScript[] {
  const now = new Date();
  return [
    {
      id: "vs-1",
      templateId: "pull-reveal",
      compositionId: "PullReveal",
      nicheId: "pokemon",
      nicheLabel: "Pokemon TCG",
      language: "EN",
      hookText: "Opening the last pack. This is either $5 or $5,000.",
      hookId: "pr-4",
      props: {},
      createdAt: new Date(now.getTime() - 2 * 86400000).toISOString(),
      status: "tracking",
      estimatedCost: 0.03,
      views: 89400,
      retention3s: 0.54,
      classification: "hit",
    },
    {
      id: "vs-2",
      templateId: "whats-it-worth",
      compositionId: "WhatsItWorth",
      nicheId: "funko",
      nicheLabel: "Funko Pop",
      language: "EN",
      hookText: "Everyone told me this was worth $50. They were wrong.",
      hookId: "wiw-2",
      props: {},
      createdAt: new Date(now.getTime() - 1 * 86400000).toISOString(),
      status: "posted",
      estimatedCost: 0.03,
      views: 34200,
      retention3s: 0.47,
      classification: "average",
    },
    {
      id: "vs-3",
      templateId: "hidden-gem",
      compositionId: "HiddenGem",
      nicheId: "lego",
      nicheLabel: "LEGO",
      language: "EN",
      hookText: "$5 thrift store find. The app says it's worth...",
      hookId: "hg-2",
      props: {},
      createdAt: new Date(now.getTime() - 3600000).toISOString(),
      status: "rendered",
      estimatedCost: 0.03,
    },
    {
      id: "vs-4",
      templateId: "market-alert",
      compositionId: "MarketAlert",
      nicheId: "yugioh",
      nicheLabel: "Yu-Gi-Oh!",
      language: "EN",
      hookText: "This just got VAULTED. Prices are already moving.",
      hookId: "ma-1",
      props: {},
      createdAt: new Date(now.getTime() - 7200000).toISOString(),
      status: "rendering",
      estimatedCost: 0.03,
    },
    {
      id: "vs-5",
      templateId: "collection-flex",
      compositionId: "CollectionFlex",
      nicheId: "watches",
      nicheLabel: "Watches",
      language: "EN",
      hookText: "The AI says my collection is worth HOW MUCH?",
      hookId: "cf-3",
      props: {},
      createdAt: now.toISOString(),
      status: "draft",
      estimatedCost: 0.03,
    },
    {
      id: "vs-6",
      templateId: "pull-reveal",
      compositionId: "PullReveal",
      nicheId: "mtg",
      nicheLabel: "Magic: The Gathering",
      language: "EN",
      hookText: "The rarest MTG pull of my life just happened",
      hookId: "pr-5",
      props: {},
      createdAt: now.toISOString(),
      status: "draft",
      estimatedCost: 0.03,
      abGroup: "A",
      abPairId: "vs-6b",
    },
    {
      id: "vs-6b",
      templateId: "pull-reveal",
      compositionId: "PullReveal",
      nicheId: "mtg",
      nicheLabel: "Magic: The Gathering",
      language: "EN",
      hookText: "PSA just graded my childhood MTG card...",
      hookId: "pr-2",
      props: {},
      createdAt: now.toISOString(),
      status: "draft",
      estimatedCost: 0.03,
      abGroup: "B",
      abPairId: "vs-6",
    },
  ];
}

function getDemoAutomationRules(): AutomationRule[] {
  return [
    {
      id: "auto-1",
      name: "Hit Replication",
      description: "When a video gets >50K views and >40% retention, auto-generate 5 hook variants for the same niche and replicate to other pods",
      trigger: "Video classified as HIT",
      action: "Generate 5 hook variants + replicate to all pods",
      isActive: true,
      lastTriggered: new Date(Date.now() - 86400000).toISOString(),
      timesTriggered: 3,
    },
    {
      id: "auto-2",
      name: "Content Velocity Gap Fill",
      description: "When a pod falls below weekly video target by Thursday, auto-generate template videos to fill the gap",
      trigger: "Pod below target by Thursday",
      action: "Auto-generate missing template videos",
      isActive: true,
      timesTriggered: 7,
    },
    {
      id: "auto-3",
      name: "Vault / Discontinuation Alert",
      description: "When demand signals detect a vault or discontinuation, auto-generate a Market Alert video",
      trigger: "Vault / OOP / discontinuation detected",
      action: "Generate MarketAlert video for affected niche",
      isActive: true,
      lastTriggered: new Date(Date.now() - 2 * 86400000).toISOString(),
      timesTriggered: 12,
    },
    {
      id: "auto-4",
      name: "A/B Hook Test",
      description: "Automatically create 2 hook variants for each generated video — post both, declare winner after 24h",
      trigger: "Every video generation",
      action: "Create variant B with next-best hook, link as A/B pair",
      isActive: true,
      lastTriggered: new Date(Date.now() - 43200000).toISOString(),
      timesTriggered: 18,
    },
    {
      id: "auto-5",
      name: "Low-Performer Hook Swap",
      description: "When a hook has 3+ consecutive fails, retire it and A/B test the next-best alternative",
      trigger: "3+ consecutive fails for same hook+niche",
      action: "Retire hook, generate with next-best untested hook",
      isActive: true,
      timesTriggered: 2,
    },
    {
      id: "auto-6",
      name: "TikTok Metrics Pull",
      description: "Auto-pull TikTok video metrics at 2h, 12h, 24h, and 7d after posting. Classify and feed into learning system.",
      trigger: "2h / 12h / 24h / 7d after posting",
      action: "Pull metrics, classify, update learning scores",
      isActive: true,
      lastTriggered: new Date(Date.now() - 7200000).toISOString(),
      timesTriggered: 42,
    },
  ];
}

// ─── Supabase Fetch ──────────────────────────────────────────────────────

async function fetchFromSupabase(): Promise<VideoScript[] | null> {
  if (!isSupabaseConfigured()) return null;
  const sb = getSupabase();
  if (!sb) return null;

  const { data, error } = await sb
    .from("ugc_video_scripts")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(50);

  if (error || !data) return null;

  return data.map((r: Record<string, unknown>) => ({
    id: r.id as string,
    templateId: r.template_id as TemplateId,
    compositionId: r.composition_id as string,
    nicheId: r.niche_id as string,
    nicheLabel: r.niche_label as string,
    language: (r.language as string) ?? "EN",
    hookText: r.hook_text as string,
    hookId: (r.hook_id as string) ?? "",
    props: (r.props as Record<string, unknown>) ?? {},
    createdAt: r.created_at as string,
    status: r.status as VideoScript["status"],
    estimatedCost: Number(r.estimated_cost) || 0.03,
    renderId: r.render_id as string | undefined,
    renderUrl: r.render_url as string | undefined,
    videoUrl: r.video_url as string | undefined,
    views: r.views_total as number | undefined,
    retention3s: r.retention_3s ? Number(r.retention_3s) : undefined,
    classification: r.classification as VideoScript["classification"],
    abGroup: r.ab_group as "A" | "B" | undefined,
    abPairId: r.ab_pair_id as string | undefined,
    abWinner: r.ab_winner as boolean | undefined,
  }));
}

// ─── Public API ──────────────────────────────────────────────────────────

export async function fetchVideoScriptsAsync(): Promise<VideoScript[]> {
  const fromDb = await fetchFromSupabase();
  return fromDb ?? getDemoScripts();
}

export function fetchVideoScripts(): VideoScript[] {
  return getDemoScripts();
}

export function fetchQueueStats(scripts: VideoScript[]): VideoQueueStats {
  const byStatus: Record<string, number> = {};
  for (const s of scripts) byStatus[s.status] = (byStatus[s.status] ?? 0) + 1;

  const nicheMap: Record<string, { nicheId: string; nicheLabel: string; count: number }> = {};
  for (const s of scripts) {
    if (!nicheMap[s.nicheId]) {
      nicheMap[s.nicheId] = { nicheId: s.nicheId, nicheLabel: s.nicheLabel, count: 0 };
    }
    nicheMap[s.nicheId].count++;
  }

  const templateMap: Record<string, { templateId: string; label: string; count: number }> = {};
  for (const s of scripts) {
    if (!templateMap[s.templateId]) {
      const t = TEMPLATES.find((t) => t.id === s.templateId);
      templateMap[s.templateId] = { templateId: s.templateId, label: t?.label ?? s.templateId, count: 0 };
    }
    templateMap[s.templateId].count++;
  }

  return {
    totalScripts: scripts.length,
    byStatus,
    estimatedCostTotal: scripts.reduce((s, v) => s + v.estimatedCost, 0),
    nicheBreakdown: Object.values(nicheMap).sort((a, b) => b.count - a.count),
    templateBreakdown: Object.values(templateMap).sort((a, b) => b.count - a.count),
  };
}

export function fetchAutomationRules(): AutomationRule[] {
  return getDemoAutomationRules();
}
