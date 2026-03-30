"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import {
  generateIdeas,
  generateSeries,
  generateWeeklyCalendar,
  generateCaptionPacks,
  planBatch,
  exportCalendarMarkdown,
  exportCaptionsMarkdown,
  exportBatchMarkdown,
  saveToLocalStorage,
  loadFromLocalStorage,
  saveBatchChecks,
  loadBatchChecks,
  PILLARS,
  ACCOUNTS,
  NICHES,
  LANGUAGES,
  LANGUAGE_LABELS,
} from "@/lib/content-machine";
import type {
  ContentIdea,
  WeeklyCalendar,
  CaptionPack,
  ContentBatch,
  LanguageCode,
  IdeaStatus,
  Priority,
} from "@/lib/content-machine";

// ─── Sub-components ──────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
      <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
      <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
      {sub && <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}

function Badge({ children, variant = "default" }: { children: React.ReactNode; variant?: "default" | "green" | "amber" | "blue" | "red" | "teal" }) {
  const colors: Record<string, string> = {
    default: "bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-gray-300",
    green: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
    amber: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    blue: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    red: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    teal: "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400",
  };
  return (
    <span role="status" className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${colors[variant]}`}>
      {children}
    </span>
  );
}

function CopyButton({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
  }, [text]);
  return (
    <button
      onClick={handleCopy}
      aria-label={copied ? "Copied to clipboard" : label ?? "Copy as Markdown"}
      className="rounded-lg border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-slate-600 transition"
    >
      {copied ? "Copied!" : label ?? "Copy Markdown"}
    </button>
  );
}

// ─── Status / Priority controls ──────────────────────────────────────────

const STATUS_OPTIONS: { value: IdeaStatus; label: string; variant: "default" | "green" | "amber" | "blue" | "red" | "teal" }[] = [
  { value: "draft", label: "Draft", variant: "default" },
  { value: "approved", label: "Approved", variant: "green" },
  { value: "scheduled", label: "Scheduled", variant: "blue" },
  { value: "filmed", label: "Filmed", variant: "teal" },
  { value: "posted", label: "Posted", variant: "green" },
  { value: "archived", label: "Archived", variant: "red" },
];

const PRIORITY_OPTIONS: { value: Priority; label: string; variant: "default" | "green" | "amber" | "blue" | "red" | "teal" }[] = [
  { value: "low", label: "Low", variant: "default" },
  { value: "normal", label: "Normal", variant: "blue" },
  { value: "high", label: "High", variant: "amber" },
  { value: "urgent", label: "Urgent", variant: "red" },
];

// ─── Ideas Tab ───────────────────────────────────────────────────────────

function IdeasTab({
  ideas,
  onUpdateIdea,
}: {
  ideas: ContentIdea[];
  onUpdateIdea: (id: string, updates: Partial<ContentIdea>) => void;
}) {
  const [pillarFilter, setPillarFilter] = useState<string>("all");
  const [accountFilter, setAccountFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    return ideas.filter((i) => {
      if (pillarFilter !== "all" && i.pillarSlug !== pillarFilter) return false;
      if (accountFilter !== "all" && i.accountHandle !== accountFilter) return false;
      if (statusFilter !== "all" && i.status !== statusFilter) return false;
      if (search && !i.hook.toLowerCase().includes(search.toLowerCase()) &&
          !i.nicheName?.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [ideas, pillarFilter, accountFilter, statusFilter, search]);

  const stats = useMemo(() => {
    const boostable = ideas.filter((i) => i.paidCandidate).length;
    const approved = ideas.filter((i) => i.status === "approved").length;
    const byObjective: Record<string, number> = {};
    for (const i of ideas) byObjective[i.objectiveType] = (byObjective[i.objectiveType] ?? 0) + 1;
    return { total: ideas.length, boostable, approved, byObjective };
  }, [ideas]);

  const pillarDist = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const i of ideas) counts[i.pillarSlug] = (counts[i.pillarSlug] ?? 0) + 1;
    return PILLARS.map((p) => ({
      ...p,
      count: counts[p.slug] ?? 0,
      pct: ideas.length > 0 ? Math.round(((counts[p.slug] ?? 0) / ideas.length) * 100) : 0,
    }));
  }, [ideas]);

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-4">
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard label="Total Ideas" value={stats.total} />
        <StatCard label="Boostable" value={stats.boostable} sub={`${ideas.length > 0 ? Math.round((stats.boostable / ideas.length) * 100) : 0}%`} />
        <StatCard label="Approved" value={stats.approved} sub={`${ideas.length > 0 ? Math.round((stats.approved / ideas.length) * 100) : 0}%`} />
        <StatCard label="Awareness" value={stats.byObjective.awareness ?? 0} />
        <StatCard label="Conversion" value={stats.byObjective.conversion ?? 0} />
      </div>

      {/* Pillar distribution */}
      <div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
        <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Pillar Distribution</p>
        <div className="flex h-6 rounded-full overflow-hidden bg-gray-100 dark:bg-slate-700" role="img" aria-label="Pillar distribution bar chart">
          {pillarDist.filter((p) => p.count > 0).map((p, idx) => (
            <div
              key={p.slug}
              className="h-full flex items-center justify-center text-[9px] font-bold text-white"
              style={{
                width: `${p.pct}%`,
                backgroundColor: `hsl(${idx * 40}, 60%, 50%)`,
                minWidth: p.pct > 0 ? "20px" : "0",
              }}
              title={`${p.emoji} ${p.name}: ${p.count} ideas (${p.pct}% actual / ${p.targetMixPct}% target)`}
            >
              {p.pct >= 8 ? `${p.emoji} ${p.pct}%` : p.emoji}
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-2 mt-2">
          {pillarDist.filter((p) => p.count > 0).map((p) => (
            <span key={p.slug} className="text-[10px] text-gray-500 dark:text-gray-400">
              {p.emoji} {p.name}: {p.count} ({p.pct}%/{p.targetMixPct}%)
            </span>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <input
          type="search"
          placeholder="Search hooks..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search ideas by hook text"
          className="rounded-lg border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200 w-40"
        />
        <select value={pillarFilter} onChange={(e) => setPillarFilter(e.target.value)} aria-label="Filter by pillar"
          className="rounded-lg border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200">
          <option value="all">All Pillars</option>
          {PILLARS.map((p) => <option key={p.slug} value={p.slug}>{p.emoji} {p.name}</option>)}
        </select>
        <select value={accountFilter} onChange={(e) => setAccountFilter(e.target.value)} aria-label="Filter by account"
          className="rounded-lg border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200">
          <option value="all">All Accounts</option>
          {ACCOUNTS.map((a) => <option key={a.handle} value={a.handle}>{a.handle}</option>)}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Filter by status"
          className="rounded-lg border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200">
          <option value="all">All Statuses</option>
          {STATUS_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <span className="text-xs text-gray-400 dark:text-gray-500 self-center">{filtered.length} ideas</span>
      </div>

      {/* Idea cards */}
      <div className="space-y-2">
        {filtered.map((idea) => {
          const isOpen = expanded.has(idea.id);
          return (
            <div key={idea.id} className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
              <button
                onClick={() => toggle(idea.id)}
                aria-expanded={isOpen}
                aria-label={`${isOpen ? "Collapse" : "Expand"} idea: ${idea.hook.slice(0, 50)}`}
                className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-slate-750 transition"
              >
                <span className="text-lg" aria-hidden="true">{idea.pillarEmoji}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-gray-900 dark:text-white truncate" title={idea.hook}>{idea.hook}</p>
                  <div className="flex gap-1.5 mt-1 flex-wrap">
                    <Badge variant="teal">{idea.format}</Badge>
                    <Badge>{idea.presenceMode.replace("_", " ")}</Badge>
                    <Badge variant="blue">{idea.objectiveType}</Badge>
                    <Badge variant={STATUS_OPTIONS.find((s) => s.value === idea.status)?.variant ?? "default"}>{idea.status}</Badge>
                    {idea.paidCandidate && <Badge variant="green">Boostable</Badge>}
                    {idea.nicheEmoji && <Badge>{idea.nicheEmoji} {idea.nicheName}</Badge>}
                  </div>
                </div>
                <span className="text-xs text-gray-400 hidden md:inline">{idea.accountHandle}</span>
                <svg className={`h-4 w-4 text-gray-400 transition-transform ${isOpen ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {isOpen && (
                <div className="px-4 pb-4 border-t border-gray-100 dark:border-slate-700 pt-3 space-y-3 text-xs">
                  {/* Status + Priority controls */}
                  <div className="flex flex-wrap gap-3">
                    <div>
                      <label className="font-medium text-gray-500 dark:text-gray-400 block mb-1">Status</label>
                      <select
                        value={idea.status}
                        onChange={(e) => onUpdateIdea(idea.id, { status: e.target.value as IdeaStatus })}
                        className="rounded border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-2 py-1 text-xs text-gray-700 dark:text-gray-200"
                      >
                        {STATUS_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="font-medium text-gray-500 dark:text-gray-400 block mb-1">Priority</label>
                      <select
                        value={idea.priority}
                        onChange={(e) => onUpdateIdea(idea.id, { priority: e.target.value as Priority })}
                        className="rounded border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-2 py-1 text-xs text-gray-700 dark:text-gray-200"
                      >
                        {PRIORITY_OPTIONS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                      </select>
                    </div>
                    <div className="flex items-end">
                      <Badge variant={PRIORITY_OPTIONS.find((p) => p.value === idea.priority)?.variant ?? "default"}>
                        {idea.priority} priority
                      </Badge>
                    </div>
                  </div>

                  <div>
                    <p className="font-medium text-gray-500 dark:text-gray-400">Concept</p>
                    <p className="text-gray-700 dark:text-gray-300">{idea.concept}</p>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div>
                      <p className="font-medium text-gray-500 dark:text-gray-400">Commerce</p>
                      <p className="text-gray-700 dark:text-gray-300">{idea.commerceMode.replace(/_/g, " ")}</p>
                    </div>
                    <div>
                      <p className="font-medium text-gray-500 dark:text-gray-400">Duration</p>
                      <p className="text-gray-700 dark:text-gray-300">{idea.estimatedDuration}</p>
                    </div>
                    <div>
                      <p className="font-medium text-gray-500 dark:text-gray-400">Target Completion</p>
                      <p className="text-gray-700 dark:text-gray-300">{idea.targetCompletionRate ? `${(idea.targetCompletionRate * 100).toFixed(0)}%` : "-"}</p>
                    </div>
                    <div>
                      <p className="font-medium text-gray-500 dark:text-gray-400">Product</p>
                      <p className="text-gray-700 dark:text-gray-300">{idea.productName ?? "\u2014"}</p>
                    </div>
                  </div>
                  {idea.boostableReason && (
                    <div>
                      <p className="font-medium text-gray-500 dark:text-gray-400">Boost Reason</p>
                      <p className="text-green-600 dark:text-green-400">{idea.boostableReason}</p>
                    </div>
                  )}
                  <div>
                    <p className="font-medium text-gray-500 dark:text-gray-400">Shot List</p>
                    <ol className="list-decimal list-inside text-gray-700 dark:text-gray-300 space-y-0.5">
                      {idea.shotList.map((s, i) => <li key={i}>{s}</li>)}
                    </ol>
                  </div>
                  {idea.voiceover && (
                    <div>
                      <p className="font-medium text-gray-500 dark:text-gray-400">Voiceover</p>
                      <p className="text-gray-700 dark:text-gray-300 italic">&ldquo;{idea.voiceover}&rdquo;</p>
                    </div>
                  )}
                  <div>
                    <p className="font-medium text-gray-500 dark:text-gray-400">SEO & Hashtags</p>
                    <p className="text-gray-700 dark:text-gray-300">
                      Keyword: <strong>{idea.targetKeyword}</strong> | {idea.hashtags.join(" ")}
                    </p>
                  </div>
                  <div>
                    <p className="font-medium text-gray-500 dark:text-gray-400">CTA</p>
                    <p className="text-[#81D8D0] font-medium">{idea.cta}</p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Calendar Tab ────────────────────────────────────────────────────────

function CalendarTab({ calendar }: { calendar: WeeklyCalendar | null }) {
  if (!calendar) return <EmptyState message="Generate a week to see the calendar." />;

  const dayGroups = useMemo(() => {
    const groups: Record<string, typeof calendar.items> = {};
    for (const item of calendar.items) {
      if (!groups[item.plannedDate]) groups[item.plannedDate] = [];
      groups[item.plannedDate].push(item);
    }
    return groups;
  }, [calendar.items]);

  const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <p className="text-sm font-medium text-gray-900 dark:text-white">{calendar.goal}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Batch film day: {calendar.batchFilmDay}</p>
        </div>
        <CopyButton text={exportCalendarMarkdown(calendar)} />
      </div>

      {/* Distribution table */}
      <div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 dark:text-gray-400">
              <th className="text-left py-1">Pillar</th>
              <th className="text-center py-1">Target</th>
              <th className="text-center py-1">Actual</th>
              <th className="text-center py-1">Status</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(calendar.pillarDistribution).map(([slug, dist]) => {
              const pillar = PILLARS.find((p) => p.slug === slug);
              const ok = Math.abs(dist.actual - dist.target) <= 5;
              return (
                <tr key={slug} className="border-t border-gray-100 dark:border-slate-700">
                  <td className="py-1.5">{pillar?.emoji} {pillar?.name ?? slug}</td>
                  <td className="text-center">{dist.target}%</td>
                  <td className="text-center">{dist.actual}%</td>
                  <td className="text-center"><Badge variant={ok ? "green" : "amber"}>{ok ? "OK" : "Adjust"}</Badge></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Warnings */}
      {calendar.warnings.length > 0 && (
        <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 p-3" role="alert">
          <p className="text-xs font-medium text-amber-700 dark:text-amber-400 mb-1">Warnings</p>
          {calendar.warnings.map((w, i) => (
            <p key={i} className="text-xs text-amber-600 dark:text-amber-400">- {w}</p>
          ))}
        </div>
      )}

      {/* 7-day grid */}
      <div className="grid grid-cols-2 md:grid-cols-7 gap-2">
        {Object.entries(dayGroups).map(([date, items]) => {
          const d = new Date(date + "T00:00:00");
          const dayName = dayNames[d.getDay()] ?? "?";
          const isBatchDay = date === calendar.batchFilmDay;
          return (
            <div
              key={date}
              className={`rounded-lg border p-3 ${
                isBatchDay
                  ? "border-[#81D8D0] bg-teal-50 dark:bg-teal-900/20"
                  : "border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800"
              }`}
            >
              <p className="text-[10px] font-bold text-gray-500 dark:text-gray-400 uppercase">
                {dayName} {date.slice(5)}
                {isBatchDay && <span className="ml-1 text-[#81D8D0]">FILM</span>}
              </p>
              <div className="mt-2 space-y-1.5">
                {items.map((item) => (
                  <div key={item.id} className="text-[10px]">
                    <p className="font-medium text-gray-700 dark:text-gray-300 truncate" title={item.idea.hook}>
                      {item.idea.pillarEmoji} {item.idea.hook.slice(0, 35)}...
                    </p>
                    <p className="text-gray-400 dark:text-gray-500">
                      {item.plannedTime} | {item.accountHandle.replace("@collectai.", "")} | {item.format}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Captions Tab ────────────────────────────────────────────────────────

function CaptionsTab({ packs }: { packs: CaptionPack[] }) {
  const [selectedLang, setSelectedLang] = useState<LanguageCode>("en");

  if (packs.length === 0) return <EmptyState message="Generate a week to see captions." />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex gap-1" role="tablist" aria-label="Language selector">
          {LANGUAGES.map((lang) => (
            <button
              key={lang}
              role="tab"
              aria-selected={selectedLang === lang}
              aria-label={LANGUAGE_LABELS[lang]}
              onClick={() => setSelectedLang(lang)}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                selectedLang === lang
                  ? "bg-[#81D8D0] text-white"
                  : "bg-gray-100 dark:bg-slate-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-slate-600"
              }`}
            >
              {lang.toUpperCase()}
            </button>
          ))}
        </div>
        <CopyButton text={exportCaptionsMarkdown(packs)} />
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        {packs.length} packs x {LANGUAGES.length} languages = {packs.length * LANGUAGES.length} captions | Viewing: {LANGUAGE_LABELS[selectedLang]}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3" role="tabpanel">
        {packs.map((pack) => {
          const c = pack.captions[selectedLang];
          if (!c) return null;
          return (
            <div key={pack.ideaId} className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 space-y-2">
              <p className="text-xs font-medium text-gray-900 dark:text-white truncate" title={pack.hook}>{pack.hook}</p>
              <div>
                <p className="text-[10px] font-medium text-gray-500 dark:text-gray-400">Organic</p>
                <p className="text-xs text-gray-700 dark:text-gray-300">{c.organic}</p>
              </div>
              <div>
                <p className="text-[10px] font-medium text-gray-500 dark:text-gray-400">Commerce</p>
                <p className="text-xs text-[#81D8D0]">{c.commerce}</p>
              </div>
              <p className="text-[10px] text-gray-400 dark:text-gray-500">{c.hashtags.join(" ")}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Batch Tab ───────────────────────────────────────────────────────────

function BatchTab({ batch }: { batch: ContentBatch | null }) {
  const [checked, setChecked] = useState<Set<string>>(() => new Set(loadBatchChecks()));

  // Persist checks
  useEffect(() => {
    saveBatchChecks(Array.from(checked));
  }, [checked]);

  if (!batch) return <EmptyState message="Generate a week to see the batch plan." />;

  const toggleCheck = (key: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const totalChecked = batch.items.filter((_, i) => checked.has(`shot-${i + 1}`)).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 flex-1 mr-4">
          <StatCard label="Videos" value={batch.items.length} />
          <StatCard label="Est. Time" value={`${batch.estimatedDurationMins}m`} />
          <StatCard label="Setup" value={batch.setupType} />
          <StatCard label="Filmed" value={`${totalChecked}/${batch.items.length}`} />
          <StatCard label="Date" value={batch.batchDate} />
        </div>
        <CopyButton text={exportBatchMarkdown(batch)} />
      </div>

      {/* Pre-checklist */}
      <div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
        <p className="text-xs font-medium text-gray-900 dark:text-white mb-2">Pre-Session Checklist</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-1">
          {batch.preChecklist.map((item, i) => {
            const key = `pre-${i}`;
            return (
              <label key={key} className="flex items-center gap-2 text-xs text-gray-700 dark:text-gray-300 cursor-pointer">
                <input type="checkbox" checked={checked.has(key)} onChange={() => toggleCheck(key)}
                  className="rounded border-gray-300 text-[#81D8D0] focus:ring-[#81D8D0]" />
                <span className={checked.has(key) ? "line-through text-gray-400" : ""}>{item}</span>
              </label>
            );
          })}
        </div>
      </div>

      {/* Shot list */}
      <div className="space-y-2">
        {batch.items.map((item) => {
          const shotKey = `shot-${item.shotOrder}`;
          return (
            <div key={item.shotOrder} className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
              <div className="flex items-start gap-3">
                <input type="checkbox" checked={checked.has(shotKey)} onChange={() => toggleCheck(shotKey)}
                  aria-label={`Mark shot ${item.shotOrder} as filmed`}
                  className="mt-1 rounded border-gray-300 text-[#81D8D0] focus:ring-[#81D8D0]" />
                <div className="flex-1 min-w-0">
                  <p className={`text-xs font-medium ${checked.has(shotKey) ? "line-through text-gray-400" : "text-gray-900 dark:text-white"}`}>
                    #{item.shotOrder} {item.idea.pillarEmoji} {item.idea.hook.slice(0, 60)}
                  </p>
                  <div className="flex gap-1.5 mt-1 flex-wrap">
                    <Badge variant="teal">{item.idea.format}</Badge>
                    <Badge>{item.idea.presenceMode.replace("_", " ")}</Badge>
                    <Badge variant="blue">{item.idea.accountHandle.replace("@collectai.", "")}</Badge>
                    {item.idea.nicheEmoji && <Badge>{item.idea.nicheEmoji}</Badge>}
                  </div>
                  <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-1">{item.setupNotes}</p>
                  <details className="mt-2">
                    <summary className="text-[10px] font-medium text-gray-500 dark:text-gray-400 cursor-pointer">Shot list & voiceover</summary>
                    <div className="mt-1 space-y-0.5">
                      {item.idea.shotList.map((s, i) => (
                        <p key={i} className="text-[10px] text-gray-600 dark:text-gray-400">{i + 1}. {s}</p>
                      ))}
                    </div>
                    {item.idea.voiceover && (
                      <p className="text-[10px] text-gray-500 dark:text-gray-400 italic mt-1">
                        VO: &ldquo;{item.idea.voiceover.slice(0, 120)}...&rdquo;
                      </p>
                    )}
                  </details>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Post tasks */}
      <div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
        <p className="text-xs font-medium text-gray-900 dark:text-white mb-2">Post-Session Tasks</p>
        {batch.postTasks.map((task, i) => {
          const key = `post-${i}`;
          return (
            <label key={key} className="flex items-center gap-2 text-xs text-gray-700 dark:text-gray-300 cursor-pointer mb-1">
              <input type="checkbox" checked={checked.has(key)} onChange={() => toggleCheck(key)}
                className="rounded border-gray-300 text-[#81D8D0] focus:ring-[#81D8D0]" />
              <span className={checked.has(key) ? "line-through text-gray-400" : ""}>{task}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}

// ─── Empty state ─────────────────────────────────────────────────────────

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-400 dark:text-gray-500">
      <svg className="h-12 w-12 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
      <p className="text-sm">{message}</p>
      <p className="text-xs mt-1">Click &ldquo;Generate Week&rdquo; to create 30 ideas, a calendar, captions, and a batch plan.</p>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────

const TABS = ["Ideas", "Calendar", "Captions", "Batch Plan"] as const;
type Tab = (typeof TABS)[number];

export function AdminContentMachine() {
  const [activeTab, setActiveTab] = useState<Tab>("Ideas");
  const [loading, setLoading] = useState(false);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);

  const [ideas, setIdeas] = useState<ContentIdea[]>([]);
  const [calendar, setCalendar] = useState<WeeklyCalendar | null>(null);
  const [captionPacks, setCaptionPacks] = useState<CaptionPack[]>([]);
  const [batch, setBatch] = useState<ContentBatch | null>(null);

  // Series generation state
  const [showSeriesModal, setShowSeriesModal] = useState(false);
  const [seriesPillar, setSeriesPillar] = useState(PILLARS[0].slug);
  const [seriesNiche, setSeriesNiche] = useState(NICHES[0].slug);

  // Restore from localStorage on mount
  useEffect(() => {
    const saved = loadFromLocalStorage();
    if (saved) {
      setIdeas(saved.ideas);
      setCalendar(saved.calendar);
      setCaptionPacks(saved.captionPacks);
      setBatch(saved.batch);
      setGeneratedAt(saved.generatedAt);
    }
  }, []);

  const handleGenerate = useCallback(() => {
    setLoading(true);
    setTimeout(() => {
      const newIdeas = generateIdeas({ count: 30 });
      const newCalendar = generateWeeklyCalendar({ ideas: newIdeas });
      const newPacks = generateCaptionPacks(newIdeas.slice(0, 15));
      const calendarIdeas = newCalendar.items.map((i) => i.idea);
      const newBatch = planBatch({ ideas: calendarIdeas, maxDurationMins: 180 });
      const now = new Date().toISOString();

      setIdeas(newIdeas);
      setCalendar(newCalendar);
      setCaptionPacks(newPacks);
      setBatch(newBatch);
      setGeneratedAt(now);
      setLoading(false);

      // Persist
      saveToLocalStorage({
        ideas: newIdeas,
        calendar: newCalendar,
        captionPacks: newPacks,
        batch: newBatch,
        generatedAt: now,
      });
    }, 100);
  }, []);

  const handleGenerateSeries = useCallback(() => {
    const seriesIdeas = generateSeries(seriesPillar, seriesNiche, 5);
    setIdeas((prev) => [...prev, ...seriesIdeas]);
    setShowSeriesModal(false);
    // Persist
    saveToLocalStorage({
      ideas: [...ideas, ...seriesIdeas],
      calendar,
      captionPacks,
      batch,
      generatedAt: generatedAt ?? new Date().toISOString(),
    });
  }, [seriesPillar, seriesNiche, ideas, calendar, captionPacks, batch, generatedAt]);

  const handleUpdateIdea = useCallback((id: string, updates: Partial<ContentIdea>) => {
    setIdeas((prev) => {
      const updated = prev.map((idea) => idea.id === id ? { ...idea, ...updates } : idea);
      // Persist
      saveToLocalStorage({
        ideas: updated,
        calendar,
        captionPacks,
        batch,
        generatedAt: generatedAt ?? new Date().toISOString(),
      });
      return updated;
    });
  }, [calendar, captionPacks, batch, generatedAt]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-lg font-bold text-gray-900 dark:text-white">Content Machine</h2>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            One-click weekly content generation: 30 ideas, calendar, 6-language captions, batch filming plan
          </p>
          {generatedAt && (
            <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
              Last generated: {new Date(generatedAt).toLocaleString()}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowSeriesModal(true)}
            disabled={loading}
            className="rounded-lg border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2 text-xs font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-slate-600 transition disabled:opacity-50"
          >
            + Series
          </button>
          <button
            onClick={handleGenerate}
            disabled={loading}
            className="rounded-lg bg-[#81D8D0] px-4 py-2 text-sm font-semibold text-white shadow hover:bg-[#5FBFB6] disabled:opacity-50 transition"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Generating...
              </span>
            ) : (
              "Generate Week"
            )}
          </button>
        </div>
      </div>

      {/* Series modal */}
      {showSeriesModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={() => setShowSeriesModal(false)}>
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-6 w-80 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-gray-900 dark:text-white mb-4">Generate Series</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-500 dark:text-gray-400 block mb-1">Pillar</label>
                <select value={seriesPillar} onChange={(e) => setSeriesPillar(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2 text-xs text-gray-700 dark:text-gray-200">
                  {PILLARS.map((p) => <option key={p.slug} value={p.slug}>{p.emoji} {p.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 dark:text-gray-400 block mb-1">Niche</label>
                <select value={seriesNiche} onChange={(e) => setSeriesNiche(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2 text-xs text-gray-700 dark:text-gray-200">
                  {NICHES.map((n) => <option key={n.slug} value={n.slug}>{n.emoji} {n.name}</option>)}
                </select>
              </div>
              <div className="flex gap-2 pt-2">
                <button onClick={() => setShowSeriesModal(false)}
                  className="flex-1 rounded-lg border border-gray-200 dark:border-slate-600 px-3 py-2 text-xs font-medium text-gray-600 dark:text-gray-300">
                  Cancel
                </button>
                <button onClick={handleGenerateSeries}
                  className="flex-1 rounded-lg bg-[#81D8D0] px-3 py-2 text-xs font-semibold text-white">
                  Generate 5-Part Series
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 dark:border-slate-700" role="tablist" aria-label="Content Machine tabs">
        {TABS.map((tab) => (
          <button
            key={tab}
            role="tab"
            aria-selected={activeTab === tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-xs font-medium transition border-b-2 ${
              activeTab === tab
                ? "border-[#81D8D0] text-[#81D8D0]"
                : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
            }`}
          >
            {tab}
            {tab === "Ideas" && ideas.length > 0 && (
              <span className="ml-1.5 rounded-full bg-gray-100 dark:bg-slate-700 px-1.5 text-[10px]">{ideas.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div role="tabpanel">
        {activeTab === "Ideas" && (ideas.length > 0 ? <IdeasTab ideas={ideas} onUpdateIdea={handleUpdateIdea} /> : <EmptyState message="No ideas yet." />)}
        {activeTab === "Calendar" && <CalendarTab calendar={calendar} />}
        {activeTab === "Captions" && <CaptionsTab packs={captionPacks} />}
        {activeTab === "Batch Plan" && <BatchTab batch={batch} />}
      </div>
    </div>
  );
}
