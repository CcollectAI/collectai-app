// ---------------------------------------------------------------------------
// Brief Template System — generates structured creator briefs from analytics
// ---------------------------------------------------------------------------

import type { UGCVideo, HookAnalysis, FormatAnalysis } from "./kpi";

// ─── Types ──────────────────────────────────────────────────────────────────

export interface BriefTemplate {
  id: string;
  title: string;
  createdAt: string;
  kitSlug: string;
  podLanguage: string;
  assignedTo: string;
  dueDate: string;
  priority: "normal" | "high" | "urgent";
  status: "draft" | "sent" | "in_progress" | "complete";

  // Creative direction
  objective: string;
  hookOptions: string[];
  format: string;
  conceptCluster: string;
  moodBoard: string[];
  dosAndDonts: { dos: string[]; donts: string[] };

  // Specs
  duration: string;
  aspectRatio: string;
  platform: string;
  cta: string;

  // Context
  inspiration: string[];       // Links to top-performing videos
  productDetails: string;
  keyMessages: string[];

  notes: string;
}

// ─── Brief Generator ────────────────────────────────────────────────────────

/**
 * Generates a brief template pre-filled with data-driven suggestions
 * based on what's currently working in the analytics.
 */
export function generateBrief(opts: {
  kitSlug: string;
  podLanguage: string;
  topHooks: HookAnalysis[];
  topFormats: FormatAnalysis[];
  topVideos: UGCVideo[];
  conceptCluster?: string;
}): BriefTemplate {
  const { kitSlug, podLanguage, topHooks, topFormats, topVideos, conceptCluster } = opts;

  // Pick best-performing hooks as suggestions
  const hookOptions = topHooks.slice(0, 3).map((h) => h.hookText);

  // Pick best format
  const bestFormat = topFormats[0]?.format ?? "tutorial";

  // Build inspiration list from top videos
  const inspiration = topVideos
    .slice(0, 3)
    .map((v) => `${v.hookText} (${formatViews(v.viewsTotal)} views, ${(v.hookRetentionRate * 100).toFixed(0)}% retention)`);

  // Auto-generate dos and donts from analytics patterns
  const avgRetention = topVideos.length > 0
    ? topVideos.reduce((s, v) => s + v.hookRetentionRate, 0) / topVideos.length
    : 0;

  const dos = [
    "Hook in first 1.5 seconds — our best videos have 40%+ 3s retention",
    `Use ${bestFormat} format — highest avg watch time in our data`,
    "Show the app scanning or revealing a price within first 3 seconds",
    "Include a specific number or stat — vague claims kill credibility",
    "Film in natural lighting, vertical 9:16, use real collectibles",
  ];

  const donts = [
    "Don't start with a brand intro or logo — start with the hook",
    "Don't use generic stock music — trending or original sounds only",
    "Don't hard-sell — let the scan result or price reveal speak for itself",
    "Don't exceed 60 seconds unless it's a deep-dive tutorial",
    "Don't mock or belittle any collection, no matter how small",
    avgRetention < 0.3 ? "Avoid slow intros — data shows we lose 70% of viewers in first 3s" : "",
  ].filter(Boolean);

  const now = new Date();
  const dueDate = new Date(now.getTime() + 5 * 86400000); // 5 days from now

  return {
    id: `brief-${Date.now()}`,
    title: `${kitSlug} — ${podLanguage} Pod`,
    createdAt: now.toISOString(),
    kitSlug,
    podLanguage,
    assignedTo: "",
    dueDate: dueDate.toISOString().slice(0, 10),
    priority: "normal",
    status: "draft",
    objective: `Create a ${bestFormat}-style video in the ${kitSlug} niche that drives app installs via scan demo or price reveal.`,
    hookOptions,
    format: bestFormat,
    conceptCluster: conceptCluster ?? topVideos[0]?.conceptCluster ?? "",
    moodBoard: [
      "Close-up of collectible item being scanned by phone",
      "Price reveal moment with genuine reaction",
      "Collection shelf or display — visually satisfying arrangement",
      "App screen showing portfolio value or price comparison",
    ],
    dosAndDonts: { dos, donts },
    duration: "15-45 seconds",
    aspectRatio: "9:16",
    platform: "TikTok + Instagram Reels",
    cta: "Scan yours free — link in bio / QR code on screen",
    inspiration,
    productDetails: `CollectAI — the AI-powered app that scans, identifies, and prices any collectible in 3 seconds across 37 marketplaces. 54 categories, 46,500+ catalog items.`,
    keyMessages: [
      "Point your phone at any collectible and know its value in seconds",
      "Search 37 marketplaces at once — never overpay again",
      "Track your collection's value over time — like a Bloomberg for your shelf",
    ],
    notes: "Tip: Use Video Generator tab to create a Remotion template video alongside this creator brief for 80/20 automated+human content split. Refer to brand.ts for voice guidelines and playbooks.ts for niche-specific cultural context.",
  };
}

/**
 * Exports a brief as a clean markdown document for sharing with creators.
 */
export function exportBriefMarkdown(brief: BriefTemplate): string {
  const lines = [
    `# Creator Brief: ${brief.title}`,
    "",
    `**Date:** ${brief.createdAt.slice(0, 10)}`,
    `**Due:** ${brief.dueDate}`,
    `**Priority:** ${brief.priority.toUpperCase()}`,
    `**Kit:** ${brief.kitSlug}`,
    `**Format:** ${brief.format}`,
    `**Platform:** ${brief.platform}`,
    `**Duration:** ${brief.duration}`,
    "",
    "---",
    "",
    "## Objective",
    brief.objective,
    "",
    "## Hook Options (pick one or create your own)",
    ...brief.hookOptions.map((h, i) => `${i + 1}. "${h}"`),
    "",
    "## Mood & Feeling",
    ...brief.moodBoard.map((m) => `- ${m}`),
    "",
    "## Do's",
    ...brief.dosAndDonts.dos.map((d) => `- ${d}`),
    "",
    "## Don'ts",
    ...brief.dosAndDonts.donts.map((d) => `- ${d}`),
    "",
    "## Key Messages",
    ...brief.keyMessages.map((m) => `- ${m}`),
    "",
    "## Product Details",
    brief.productDetails,
    "",
    "## Inspiration (what's working now)",
    ...brief.inspiration.map((i) => `- ${i}`),
    "",
    "## CTA",
    brief.cta,
    "",
    "---",
    `*Generated by CollectAI Admin — ${brief.createdAt.slice(0, 10)}*`,
  ];
  return lines.join("\n");
}

/**
 * Generates a WhatsApp-friendly brief summary (shorter, plain text).
 */
export function exportBriefWhatsApp(brief: BriefTemplate): string {
  const lines = [
    `*NEW BRIEF: ${brief.title}*`,
    `Due: ${brief.dueDate} | Priority: ${brief.priority}`,
    "",
    `Kit: ${brief.kitSlug}`,
    `Format: ${brief.format} | ${brief.duration}`,
    "",
    `*Hook options:*`,
    ...brief.hookOptions.map((h, i) => `${i + 1}. "${h}"`),
    "",
    `*Key points:*`,
    ...brief.dosAndDonts.dos.slice(0, 3).map((d) => `- ${d}`),
    "",
    `*Inspiration:*`,
    ...brief.inspiration.slice(0, 2).map((i) => `- ${i}`),
    "",
    `CTA: ${brief.cta}`,
  ];
  return lines.join("\n");
}

function formatViews(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}
