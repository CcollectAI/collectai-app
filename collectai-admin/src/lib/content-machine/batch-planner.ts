// ---------------------------------------------------------------------------
// Content Machine — Batch Filming Planner for CollectAI
// Groups ideas by setup type and generates shot-by-shot filming plans
// ---------------------------------------------------------------------------

import type {
  ContentIdea,
  ContentBatch,
  BatchItem,
  PresenceMode,
  ContentFormat,
  GenerateBatchOptions,
} from "./types";

// ─── Time estimates ──────────────────────────────────────────────────────

const SETUP_TIME_MINS: Record<PresenceMode, number> = {
  face: 5,
  voiceover: 3,
  hands_only: 2,
  text_only: 1,
};

const FILMING_TIME_MINS: Record<ContentFormat, number> = {
  tutorial: 20,
  timelapse: 10,
  POV: 8,
  unboxing: 12,
  ASMR: 15,
  routine: 10,
  reveal: 10,
  comparison: 15,
  transformation: 12,
  "fix-it": 12,
  lifestyle: 10,
  "top-list": 15,
};

// ─── Pre-session checklist ───────────────────────────────────────────────

const PRE_CHECKLIST = [
  "Phone charged to 100%",
  "Ring light / key light set up",
  "Tripod positioned",
  "Microphone tested (lapel or shotgun)",
  "Background clean / display shelf arranged",
  "All collectible items laid out in filming order",
  "CollectAI app open and logged in",
  "Water bottle nearby",
  "Do Not Disturb mode enabled",
  "SD card / storage checked (min 10 GB free)",
];

// ─── Post-session tasks ──────────────────────────────────────────────────

const POST_TASKS = [
  "Transfer footage to editing folder",
  "Label each clip: [date]_[template]_[niche]_[take]",
  "Update content pipeline status to 'editing'",
  "Back up raw footage to cloud",
  "Note any retakes needed",
];

// ─── Setup notes per presence mode ───────────────────────────────────────

function getSetupNotes(presence: PresenceMode, format: ContentFormat): string {
  const notes: string[] = [];

  switch (presence) {
    case "face":
      notes.push("Camera at eye level, good lighting on face");
      notes.push("Check framing: head + shoulders + item space");
      break;
    case "voiceover":
      notes.push("Record voiceover separately in quiet room");
      notes.push("Film B-roll of items from multiple angles");
      break;
    case "hands_only":
      notes.push("Top-down camera angle on clean surface");
      notes.push("Ensure hands and items fill the frame");
      break;
    case "text_only":
      notes.push("Pre-design text overlays before filming");
      notes.push("Film clean B-roll for background");
      break;
  }

  switch (format) {
    case "unboxing":
      notes.push("Keep packaging sealed until camera is rolling");
      break;
    case "ASMR":
      notes.push("External mic close to items, minimize ambient noise");
      break;
    case "comparison":
      notes.push("Lay both items side-by-side in frame");
      break;
    case "reveal":
      notes.push("Cover/blur item initially, have reveal transition planned");
      break;
    case "timelapse":
      notes.push("Set up fixed camera position, ensure stable tripod");
      break;
  }

  return notes.join(". ");
}

// ─── Main planner ────────────────────────────────────────────────────────

export function planBatch(opts: GenerateBatchOptions = {}): ContentBatch {
  const maxMins = opts.maxDurationMins ?? 180;
  const batchDate = opts.batchDate ?? new Date().toISOString().split("T")[0];
  const ideas = opts.ideas ?? [];

  // Sort by presence mode to minimize setup changes
  const sorted = [...ideas].sort((a, b) => {
    const presenceOrder: Record<PresenceMode, number> = { hands_only: 0, voiceover: 1, face: 2, text_only: 3 };
    return (presenceOrder[a.presenceMode] ?? 9) - (presenceOrder[b.presenceMode] ?? 9);
  });

  // Fill batch up to max duration
  const batchItems: BatchItem[] = [];
  let totalMins = 0;
  let lastPresence: PresenceMode | null = null;

  for (const idea of sorted) {
    const setupTime = idea.presenceMode !== lastPresence ? SETUP_TIME_MINS[idea.presenceMode] : 0;
    const filmTime = FILMING_TIME_MINS[idea.format] ?? 10;
    const ideaTime = setupTime + filmTime;

    if (totalMins + ideaTime > maxMins) break;

    batchItems.push({
      idea,
      shotOrder: batchItems.length + 1,
      setupNotes: getSetupNotes(idea.presenceMode, idea.format),
    });

    totalMins += ideaTime;
    lastPresence = idea.presenceMode;
  }

  // Determine dominant setup type
  const presenceCounts: Record<string, number> = {};
  for (const item of batchItems) {
    const p = item.idea.presenceMode;
    presenceCounts[p] = (presenceCounts[p] ?? 0) + 1;
  }
  const dominantSetup = Object.entries(presenceCounts)
    .sort((a, b) => b[1] - a[1])[0]?.[0] ?? "mixed";

  return {
    id: `batch-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    title: `Batch Filming — ${batchDate}`,
    batchDate,
    setupType: batchItems.length > 0 && presenceCounts[dominantSetup] === batchItems.length
      ? dominantSetup
      : "mixed",
    estimatedDurationMins: totalMins,
    items: batchItems,
    preChecklist: PRE_CHECKLIST,
    postTasks: POST_TASKS,
  };
}

// ─── Markdown export ─────────────────────────────────────────────────────

export function exportBatchMarkdown(batch: ContentBatch): string {
  const lines: string[] = [
    `# ${batch.title}`,
    "",
    `**Date:** ${batch.batchDate}`,
    `**Videos:** ${batch.items.length}`,
    `**Estimated Time:** ${batch.estimatedDurationMins} minutes`,
    `**Setup Type:** ${batch.setupType}`,
    "",
    "## Pre-Session Checklist",
    "",
  ];

  for (const item of batch.preChecklist) {
    lines.push(`- [ ] ${item}`);
  }

  lines.push("", "## Shot List", "");

  // Group by presence mode
  const byPresence: Record<string, BatchItem[]> = {};
  for (const item of batch.items) {
    const key = item.idea.presenceMode;
    if (!byPresence[key]) byPresence[key] = [];
    byPresence[key].push(item);
  }

  for (const [presence, items] of Object.entries(byPresence)) {
    const setupTime = SETUP_TIME_MINS[presence as PresenceMode] ?? 2;
    lines.push(`### Setup: ${presence.replace("_", " ")} (${setupTime}min setup)`);
    lines.push("");

    for (const item of items) {
      const filmTime = FILMING_TIME_MINS[item.idea.format] ?? 10;
      lines.push(`#### ${item.shotOrder}. ${item.idea.pillarEmoji} ${item.idea.hook.slice(0, 60)}`);
      lines.push(`- **Format:** ${item.idea.format} | **Duration:** ~${filmTime}min`);
      lines.push(`- **Account:** ${item.idea.accountHandle}`);
      if (item.idea.nicheEmoji) lines.push(`- **Niche:** ${item.idea.nicheEmoji} ${item.idea.nicheName}`);
      lines.push(`- **Setup:** ${item.setupNotes}`);
      lines.push("");

      lines.push("**Shots:**");
      for (const shot of item.idea.shotList) {
        lines.push(`- [ ] ${shot}`);
      }

      if (item.idea.voiceover) {
        lines.push("");
        lines.push(`**Voiceover:** _"${item.idea.voiceover}"_`);
      }
      lines.push("");
    }
  }

  lines.push("## Post-Session Tasks", "");
  for (const task of batch.postTasks) {
    lines.push(`- [ ] ${task}`);
  }

  return lines.join("\n");
}
