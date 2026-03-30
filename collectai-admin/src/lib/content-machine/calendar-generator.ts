// ---------------------------------------------------------------------------
// Content Machine — Calendar Generator for CollectAI
// Distributes ideas across a week with pillar mix enforcement
// ---------------------------------------------------------------------------

import type {
  ContentIdea,
  WeeklyCalendar,
  CalendarItem,
  GenerateCalendarOptions,
} from "./types";
import {
  PILLARS,
  ACCOUNT_BY_PILLAR,
  ACCOUNT_WEEKLY_TARGETS,
  WEEKLY_MINIMUMS,
  POSTING_TIMES,
} from "./seed-data";
import { generateIdeas } from "./idea-generator";

const DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] as const;

function getMonday(dateStr?: string): Date {
  const d = dateStr ? new Date(dateStr) : new Date();
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(d);
  monday.setDate(diff);
  monday.setHours(0, 0, 0, 0);
  return monday;
}

function formatDate(d: Date): string {
  return d.toISOString().split("T")[0];
}

function addDays(d: Date, n: number): Date {
  const result = new Date(d);
  result.setDate(result.getDate() + n);
  return result;
}

function uid(): string {
  return `cal-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

// ─── Main generator ──────────────────────────────────────────────────────

export function generateWeeklyCalendar(opts: GenerateCalendarOptions = {}): WeeklyCalendar {
  const monday = getMonday(opts.weekStart);
  const batchDayIndex = opts.batchFilmDay
    ? DAY_NAMES.indexOf(opts.batchFilmDay)
    : 2; // Wednesday default

  // Get or generate ideas
  const totalNeeded = Object.values(ACCOUNT_WEEKLY_TARGETS).reduce((a, b) => a + b, 0);
  const ideas = opts.ideas?.length
    ? opts.ideas
    : generateIdeas({ count: Math.max(totalNeeded + 5, 30) });

  // Step 1: Fill weekly minimums first
  const scheduled: { idea: ContentIdea; dayIndex: number }[] = [];
  const usedIds = new Set<string>();
  const pillarCounts: Record<string, number> = {};
  const accountCounts: Record<string, number> = {};

  for (const [pillarSlug, minCount] of Object.entries(WEEKLY_MINIMUMS)) {
    for (let i = 0; i < minCount; i++) {
      const idea = ideas.find((id) => id.pillarSlug === pillarSlug && !usedIds.has(id.id));
      if (!idea) continue;
      usedIds.add(idea.id);
      pillarCounts[pillarSlug] = (pillarCounts[pillarSlug] ?? 0) + 1;
      const account = idea.accountHandle;
      accountCounts[account] = (accountCounts[account] ?? 0) + 1;
      scheduled.push({ idea, dayIndex: -1 }); // day assigned later
    }
  }

  // Step 2: Fill remaining slots weighted by pillar mix
  const remaining = totalNeeded - scheduled.length;
  for (let i = 0; i < remaining; i++) {
    // Find accounts still below target
    const underserved = Object.entries(ACCOUNT_WEEKLY_TARGETS)
      .filter(([acc, target]) => (accountCounts[acc] ?? 0) < target)
      .map(([acc]) => acc);

    if (underserved.length === 0) break;

    const targetAccount = underserved[i % underserved.length];
    const availableIdeas = ideas.filter((id) => {
      if (usedIds.has(id.id)) return false;
      return ACCOUNT_BY_PILLAR[id.pillarSlug] === targetAccount || id.accountHandle === targetAccount;
    });

    const idea = availableIdeas[0] ?? ideas.find((id) => !usedIds.has(id.id));
    if (!idea) break;

    usedIds.add(idea.id);
    pillarCounts[idea.pillarSlug] = (pillarCounts[idea.pillarSlug] ?? 0) + 1;
    accountCounts[idea.accountHandle] = (accountCounts[idea.accountHandle] ?? 0) + 1;
    scheduled.push({ idea, dayIndex: -1 });
  }

  // Step 3: Distribute across Mon-Sun, skip batch film day
  const availableDays = DAY_NAMES
    .map((_, i) => i)
    .filter((i) => i !== batchDayIndex);

  // Spread evenly, favoring days with prime posting times
  const postsPerDay: number[] = Array(7).fill(0);
  for (let i = 0; i < scheduled.length; i++) {
    const dayIndex = availableDays[i % availableDays.length];
    scheduled[i].dayIndex = dayIndex;
    postsPerDay[dayIndex]++;
  }

  // Build calendar items
  const items: CalendarItem[] = scheduled.map((s, idx) => {
    const dayDate = addDays(monday, s.dayIndex);
    const timeSlot = POSTING_TIMES[idx % POSTING_TIMES.length];
    return {
      id: uid(),
      ideaId: s.idea.id,
      idea: s.idea,
      accountHandle: s.idea.accountHandle,
      plannedDate: formatDate(dayDate),
      plannedTime: timeSlot,
      languageCode: s.idea.languageCode,
      status: "planned",
      format: s.idea.format,
    };
  });

  // Sort by date then time
  items.sort((a, b) => {
    const dateComp = a.plannedDate.localeCompare(b.plannedDate);
    return dateComp !== 0 ? dateComp : a.plannedTime.localeCompare(b.plannedTime);
  });

  // Step 4: Calculate distribution
  const pillarDistribution: Record<string, { target: number; actual: number }> = {};
  for (const pillar of PILLARS) {
    const actual = pillarCounts[pillar.slug] ?? 0;
    const actualPct = scheduled.length > 0 ? Math.round((actual / scheduled.length) * 100) : 0;
    pillarDistribution[pillar.slug] = {
      target: pillar.targetMixPct,
      actual: actualPct,
    };
  }

  // Step 5: Warnings
  const warnings = validateMix(pillarCounts, accountCounts, items);

  return {
    id: uid(),
    weekStart: formatDate(monday),
    goal: `Generate ${scheduled.length} posts across 3 accounts with balanced pillar mix`,
    notes: `Batch filming day: ${DAY_NAMES[batchDayIndex]}. ${warnings.length} warnings.`,
    pillarDistribution,
    batchFilmDay: formatDate(addDays(monday, batchDayIndex)),
    items,
    warnings,
  };
}

// ─── Mix validation ──────────────────────────────────────────────────────

function validateMix(
  pillarCounts: Record<string, number>,
  accountCounts: Record<string, number>,
  items: CalendarItem[]
): string[] {
  const warnings: string[] = [];

  // Check pillar minimums
  for (const [slug, min] of Object.entries(WEEKLY_MINIMUMS)) {
    if (min > 0 && (pillarCounts[slug] ?? 0) < min) {
      const pillar = PILLARS.find((p) => p.slug === slug);
      warnings.push(`${pillar?.emoji ?? ""} ${pillar?.name ?? slug} below minimum (${pillarCounts[slug] ?? 0}/${min})`);
    }
  }

  // Check account targets
  for (const [account, target] of Object.entries(ACCOUNT_WEEKLY_TARGETS)) {
    const actual = accountCounts[account] ?? 0;
    if (actual < target) {
      warnings.push(`${account} below target (${actual}/${target} posts)`);
    }
  }

  // Check for >3 posts on a single day
  const dayCount: Record<string, number> = {};
  for (const item of items) {
    dayCount[item.plannedDate] = (dayCount[item.plannedDate] ?? 0) + 1;
  }
  for (const [date, count] of Object.entries(dayCount)) {
    if (count > 3) {
      warnings.push(`${date} has ${count} posts (>3 may overwhelm feed)`);
    }
  }

  // Check presence mode concentration
  const presenceCounts: Record<string, number> = {};
  for (const item of items) {
    const mode = item.idea.presenceMode;
    presenceCounts[mode] = (presenceCounts[mode] ?? 0) + 1;
  }
  for (const [mode, count] of Object.entries(presenceCounts)) {
    if (items.length > 0 && count / items.length > 0.7) {
      warnings.push(`>70% of posts use ${mode} presence — consider more variety`);
    }
  }

  return warnings;
}

// ─── Markdown export ─────────────────────────────────────────────────────

export function exportCalendarMarkdown(cal: WeeklyCalendar): string {
  const lines: string[] = [
    `# Content Calendar — Week of ${cal.weekStart}`,
    "",
    `**Goal:** ${cal.goal}`,
    `**Batch Film Day:** ${cal.batchFilmDay}`,
    "",
    "## Pillar Distribution",
    "",
    "| Pillar | Target | Actual | Status |",
    "|--------|--------|--------|--------|",
  ];

  for (const [slug, dist] of Object.entries(cal.pillarDistribution)) {
    const pillar = PILLARS.find((p) => p.slug === slug);
    const status = Math.abs(dist.actual - dist.target) <= 5 ? "OK" : "Adjust";
    lines.push(`| ${pillar?.emoji ?? ""} ${pillar?.name ?? slug} | ${dist.target}% | ${dist.actual}% | ${status} |`);
  }

  lines.push("", "## Schedule", "");

  // Group by date
  const byDate: Record<string, CalendarItem[]> = {};
  for (const item of cal.items) {
    if (!byDate[item.plannedDate]) byDate[item.plannedDate] = [];
    byDate[item.plannedDate].push(item);
  }

  for (const [date, dateItems] of Object.entries(byDate)) {
    const d = new Date(date);
    const dayName = DAY_NAMES[((d.getDay() + 6) % 7)];
    lines.push(`### ${dayName.charAt(0).toUpperCase() + dayName.slice(1)} — ${date}`);
    lines.push("");
    for (const item of dateItems) {
      lines.push(`- **${item.plannedTime}** | ${item.accountHandle} | ${item.idea.pillarEmoji} ${item.idea.hook.slice(0, 60)}`);
      lines.push(`  Format: ${item.format} | Presence: ${item.idea.presenceMode}`);
    }
    lines.push("");
  }

  if (cal.warnings.length > 0) {
    lines.push("## Warnings", "");
    for (const w of cal.warnings) lines.push(`- ${w}`);
  }

  return lines.join("\n");
}
