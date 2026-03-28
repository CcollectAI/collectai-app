"use client";

import { useEffect, useState, useMemo } from "react";
import {
  fetchSwipeFileData,
} from "@/lib/kpi";
import { AdminDemoBanner } from "@/components/AdminDemoBanner";
import type { SwipeFileData, SwipeFileEntry } from "@/lib/kpi";

/* ── Helpers ─────────────────────────────────────────────────────────────── */

function formatNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-[#0D1B2A]">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-400">{sub}</p>}
    </div>
  );
}

const HOOK_TYPE_COLORS: Record<string, string> = {
  question: "bg-blue-100 text-blue-700",
  shock: "bg-red-100 text-red-700",
  curiosity: "bg-purple-100 text-purple-700",
  relatable: "bg-amber-100 text-amber-700",
  tutorial: "bg-emerald-100 text-emerald-700",
  challenge: "bg-pink-100 text-pink-700",
  transformation: "bg-indigo-100 text-indigo-700",
  story: "bg-teal-100 text-teal-700",
};

const FORMAT_COLORS: Record<string, string> = {
  "talking-head": "bg-sky-100 text-sky-700",
  "green-screen": "bg-lime-100 text-lime-700",
  voiceover: "bg-orange-100 text-orange-700",
  timelapse: "bg-cyan-100 text-cyan-700",
  duet: "bg-fuchsia-100 text-fuchsia-700",
  stitch: "bg-rose-100 text-rose-700",
  slideshow: "bg-violet-100 text-violet-700",
  skit: "bg-yellow-100 text-yellow-700",
};

const PLATFORM_BADGE: Record<string, { bg: string; label: string }> = {
  tiktok: { bg: "bg-black text-white", label: "TikTok" },
  instagram: { bg: "bg-gradient-to-r from-purple-500 to-pink-500 text-white", label: "IG" },
};

type SortKey = "views" | "date" | "hookType";

/* ── Component ───────────────────────────────────────────────────────────── */

export function AdminSwipeFile() {
  const [data, setData] = useState<SwipeFileData | null>(null);
  const [loading, setLoading] = useState(true);

  // Filters
  const [hookFilter, setHookFilter] = useState<string>("all");
  const [formatFilter, setFormatFilter] = useState<string>("all");
  const [competitorOnly, setCompetitorOnly] = useState(false);
  const [tagSearch, setTagSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortKey>("views");

  useEffect(() => {
    setLoading(true);
    fetchSwipeFileData().then((d) => {
      setData(d);
      setLoading(false);
    });
  }, []);

  const hookTypes = useMemo(() => (data ? Object.keys(data.byHookType) : []), [data]);
  const formats = useMemo(() => (data ? Object.keys(data.byFormat) : []), [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    let entries = [...data.entries];

    if (hookFilter !== "all") entries = entries.filter((e) => e.hookType === hookFilter);
    if (formatFilter !== "all") entries = entries.filter((e) => e.format === formatFilter);
    if (competitorOnly) entries = entries.filter((e) => e.isCompetitor);
    if (tagSearch.trim()) {
      const q = tagSearch.toLowerCase();
      entries = entries.filter((e) => e.tags.some((t) => t.toLowerCase().includes(q)));
    }

    entries.sort((a, b) => {
      if (sortBy === "views") return b.estimatedViews - a.estimatedViews;
      if (sortBy === "date") return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
      return a.hookType.localeCompare(b.hookType);
    });

    return entries;
  }, [data, hookFilter, formatFilter, competitorOnly, tagSearch, sortBy]);

  /* ── Loading ─────────────────────────────────────────────────────────── */

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-[#FF6B6B]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#0D1B2A]">Swipe File / Inspiration Library</h2>
          <AdminDemoBanner />
        </div>
        <p className="text-xs text-gray-400">{filtered.length} of {data.totalEntries} entries</p>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total Entries" value={String(data.totalEntries)} />
        <StatCard label="Hook Types" value={String(hookTypes.length)} />
        <StatCard label="Formats" value={String(formats.length)} />
        <StatCard
          label="Competitor Entries"
          value={String(data.entries.filter((e) => e.isCompetitor).length)}
        />
      </div>

      {/* Hook type breakdown pills */}
      <div>
        <h3 className="mb-2 text-sm font-bold uppercase tracking-wider text-gray-500">By Hook Type</h3>
        <div className="flex flex-wrap gap-2">
          {Object.entries(data.byHookType).map(([type, count]) => (
            <span
              key={type}
              className={`rounded-full px-3 py-1 text-xs font-semibold ${HOOK_TYPE_COLORS[type] || "bg-gray-100 text-gray-600"}`}
            >
              {type} ({count})
            </span>
          ))}
        </div>
      </div>

      {/* Format breakdown pills */}
      <div>
        <h3 className="mb-2 text-sm font-bold uppercase tracking-wider text-gray-500">By Format</h3>
        <div className="flex flex-wrap gap-2">
          {Object.entries(data.byFormat).map(([fmt, count]) => (
            <span
              key={fmt}
              className={`rounded-full px-3 py-1 text-xs font-semibold ${FORMAT_COLORS[fmt] || "bg-gray-100 text-gray-600"}`}
            >
              {fmt} ({count})
            </span>
          ))}
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl bg-gray-50 p-4">
        <select
          value={hookFilter}
          onChange={(e) => setHookFilter(e.target.value)}
          className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-semibold text-gray-600"
        >
          <option value="all">All hook types</option>
          {hookTypes.map((h) => (
            <option key={h} value={h}>{h}</option>
          ))}
        </select>

        <select
          value={formatFilter}
          onChange={(e) => setFormatFilter(e.target.value)}
          className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-semibold text-gray-600"
        >
          <option value="all">All formats</option>
          {formats.map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>

        <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-600">
          <input
            type="checkbox"
            checked={competitorOnly}
            onChange={(e) => setCompetitorOnly(e.target.checked)}
            className="rounded border-gray-300"
          />
          Competitors only
        </label>

        <input
          type="text"
          placeholder="Search tags..."
          value={tagSearch}
          onChange={(e) => setTagSearch(e.target.value)}
          className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 placeholder:text-gray-300"
        />

        <div className="ml-auto flex items-center gap-2">
          <span className="text-[10px] font-semibold uppercase text-gray-400">Sort</span>
          {(["views", "date", "hookType"] as SortKey[]).map((s) => (
            <button
              key={s}
              onClick={() => setSortBy(s)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                sortBy === s
                  ? "bg-[#0D1B2A] text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {s === "hookType" ? "Hook Type" : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Card grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((entry) => (
          <SwipeCard key={entry.id} entry={entry} />
        ))}
        {filtered.length === 0 && (
          <p className="col-span-full py-12 text-center text-sm text-gray-400">No entries match your filters.</p>
        )}
      </div>
    </div>
  );
}

/* ── Swipe Card ──────────────────────────────────────────────────────────── */

function SwipeCard({ entry }: { entry: SwipeFileEntry }) {
  const platform = PLATFORM_BADGE[entry.platform.toLowerCase()] || { bg: "bg-gray-200 text-gray-700", label: entry.platform };

  return (
    <div
      className={`rounded-xl bg-white p-4 shadow-sm transition hover:shadow-md ${
        entry.isCompetitor ? "ring-2 ring-red-400" : ""
      }`}
    >
      {/* Source + Platform */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-500">@{entry.sourceAccount}</span>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${platform.bg}`}>
          {platform.label}
        </span>
      </div>

      {/* Hook text */}
      <p className="mt-2 text-sm font-bold leading-snug text-[#0D1B2A]">{entry.hookText}</p>

      {/* Badges */}
      <div className="mt-2 flex flex-wrap gap-1.5">
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${HOOK_TYPE_COLORS[entry.hookType] || "bg-gray-100 text-gray-600"}`}>
          {entry.hookType}
        </span>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${FORMAT_COLORS[entry.format] || "bg-gray-100 text-gray-600"}`}>
          {entry.format}
        </span>
        {entry.isCompetitor && (
          <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-bold text-red-700">
            Competitor
          </span>
        )}
      </div>

      {/* Why it works */}
      <p className="mt-2 text-xs leading-relaxed text-gray-500">{entry.whyItWorks}</p>

      {/* Views */}
      <p className="mt-2 text-xs font-semibold tabular-nums text-gray-400">
        {formatNum(entry.estimatedViews)} est. views
      </p>

      {/* Tags */}
      {entry.tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {entry.tags.map((tag) => (
            <span key={tag} className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] text-gray-500">
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Link */}
      <a
        href={entry.url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-3 inline-block text-xs font-semibold text-blue-600 hover:underline"
      >
        View original &rarr;
      </a>
    </div>
  );
}
