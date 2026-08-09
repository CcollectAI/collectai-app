"use client";

import { useEffect, useState, useMemo } from "react";
import { fetchSwipeFileData } from "@/lib/kpi";
import { MetricCard } from "@/components/ui/MetricCard";
import type { SwipeFileData, SwipeFileEntry } from "@/lib/kpi";
import { AdminDemoBanner } from "@/components/AdminDemoBanner";

/* ───────────────────────── Helpers ───────────────────────── */

function formatNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

/* ───────────────────────── Color Maps ───────────────────────── */

const HOOK_TYPE_COLORS: Record<string, { pill: string; pillActive: string; border: string; bar: string }> = {
  question:       { pill: "border-blue-300 text-blue-600 dark:border-blue-500 dark:text-blue-400",       pillActive: "bg-blue-600 text-white border-blue-600 dark:bg-blue-500 dark:border-blue-500",       border: "bg-blue-500",    bar: "bg-blue-500" },
  shock:          { pill: "border-red-300 text-red-600 dark:border-red-500 dark:text-red-400",            pillActive: "bg-red-600 text-white border-red-600 dark:bg-red-500 dark:border-red-500",            border: "bg-red-500",     bar: "bg-red-500" },
  curiosity:      { pill: "border-purple-300 text-purple-600 dark:border-purple-500 dark:text-purple-400", pillActive: "bg-purple-600 text-white border-purple-600 dark:bg-purple-500 dark:border-purple-500", border: "bg-purple-500",  bar: "bg-purple-500" },
  relatable:      { pill: "border-amber-300 text-amber-600 dark:border-amber-500 dark:text-amber-400",    pillActive: "bg-amber-600 text-white border-amber-600 dark:bg-amber-500 dark:border-amber-500",    border: "bg-amber-500",   bar: "bg-amber-500" },
  tutorial:       { pill: "border-emerald-300 text-emerald-600 dark:border-emerald-500 dark:text-emerald-400", pillActive: "bg-emerald-600 text-white border-emerald-600 dark:bg-emerald-500 dark:border-emerald-500", border: "bg-emerald-500", bar: "bg-emerald-500" },
  challenge:      { pill: "border-pink-300 text-pink-600 dark:border-pink-500 dark:text-pink-400",        pillActive: "bg-pink-600 text-white border-pink-600 dark:bg-pink-500 dark:border-pink-500",        border: "bg-pink-500",    bar: "bg-pink-500" },
  transformation: { pill: "border-indigo-300 text-indigo-600 dark:border-indigo-500 dark:text-indigo-400", pillActive: "bg-indigo-600 text-white border-indigo-600 dark:bg-indigo-500 dark:border-indigo-500", border: "bg-indigo-500",  bar: "bg-indigo-500" },
  story:          { pill: "border-teal-300 text-teal-600 dark:border-teal-500 dark:text-teal-400",        pillActive: "bg-teal-600 text-white border-teal-600 dark:bg-teal-500 dark:border-teal-500",        border: "bg-teal-500",    bar: "bg-teal-500" },
};

const HOOK_CHIP_COLORS: Record<string, string> = {
  question: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  shock: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  curiosity: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  relatable: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  tutorial: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  challenge: "bg-pink-100 text-pink-700 dark:bg-pink-900/40 dark:text-pink-300",
  transformation: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300",
  story: "bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300",
};

const FORMAT_COLORS: Record<string, string> = {
  "talking-head": "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300",
  "green-screen": "bg-lime-100 text-lime-700 dark:bg-lime-900/40 dark:text-lime-300",
  voiceover: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
  timelapse: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300",
  duet: "bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-900/40 dark:text-fuchsia-300",
  stitch: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
  slideshow: "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300",
  skit: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300",
};

const FORMAT_BAR_COLORS: Record<string, string> = {
  "talking-head": "bg-sky-500",
  "green-screen": "bg-lime-500",
  voiceover: "bg-orange-500",
  timelapse: "bg-cyan-500",
  duet: "bg-fuchsia-500",
  stitch: "bg-rose-500",
  slideshow: "bg-violet-500",
  skit: "bg-yellow-500",
};

const PLATFORM_BADGE: Record<string, { bg: string; label: string }> = {
  tiktok: { bg: "bg-black text-white", label: "TikTok" },
  instagram: { bg: "bg-gradient-to-r from-purple-500 to-pink-500 text-white", label: "IG" },
};

type SortKey = "views" | "date" | "hookType";

const cardCls = "bg-white dark:bg-slate-800 rounded-2xl shadow-sm p-5 transition-colors";
const selectCls = "rounded-lg border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-1.5 text-xs font-semibold text-gray-600 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-[#81D8D0]/50";

/* ───────────────────────── Distribution Bar Card ───────────────────────── */

function DistributionCard({
  title,
  data,
  colorMap,
}: {
  title: string;
  data: Record<string, number>;
  colorMap: Record<string, string>;
}) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = entries.length > 0 ? entries[0][1] : 1;

  return (
    <div className={cardCls}>
      <AdminDemoBanner source="swipe" />

      <h2 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">{title}</h2>
      <div className="space-y-2">
        {entries.map(([name, count]) => (
          <div key={name} className="flex items-center gap-3">
            <span className="text-xs text-gray-600 dark:text-gray-300 w-28 truncate capitalize">{name.replace(/-/g, " ")}</span>
            <div className="flex-1 h-5 bg-gray-100 dark:bg-slate-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ${colorMap[name] || "bg-gray-400"}`}
                style={{ width: `${(count / max) * 100}%` }}
              />
            </div>
            <span className="text-xs font-semibold tabular-nums text-gray-500 dark:text-gray-400 w-8 text-right">{count}</span>
          </div>
        ))}
        {entries.length === 0 && (
          <p className="text-xs text-gray-400 dark:text-gray-500 text-center py-4">No data</p>
        )}
      </div>
    </div>
  );
}

/* ───────────────────────── Swipe Card ───────────────────────── */

function SwipeCard({ entry }: { entry: SwipeFileEntry }) {
  const platform = PLATFORM_BADGE[entry.platform.toLowerCase()] || {
    bg: "bg-gray-200 text-gray-700 dark:bg-slate-600 dark:text-slate-300",
    label: entry.platform,
  };

  const hookColors = HOOK_TYPE_COLORS[entry.hookType] || {
    pill: "border-gray-300 text-gray-600",
    pillActive: "bg-gray-600 text-white border-gray-600",
    border: "bg-gray-400",
    bar: "bg-gray-400",
  };

  return (
    <div
      className={`group bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-gray-100 dark:border-slate-700 overflow-hidden transition hover:shadow-lg hover:-translate-y-0.5 ${
        entry.isCompetitor ? "ring-2 ring-red-400/60 dark:ring-red-500/40" : ""
      }`}
    >
      {/* Colored header bar */}
      <div className={`h-[3px] ${hookColors.border}`} />

      {/* Card body */}
      <div className="p-5">
        {/* Top row: platform badge + competitor + source */}
        <div className="flex items-center gap-2">
          <span className={`rounded-lg px-2.5 py-1 text-[10px] font-bold leading-none ${platform.bg}`}>
            {platform.label}
          </span>
          {entry.isCompetitor && (
            <span className="rounded-full bg-red-100 dark:bg-red-900/30 px-2 py-0.5 text-[10px] font-bold text-red-600 dark:text-red-400">
              Competitor
            </span>
          )}
          <span className="ml-auto text-[11px] font-medium text-gray-400 dark:text-slate-500 truncate max-w-[120px]">
            @{entry.sourceAccount}
          </span>
        </div>

        {/* Hook text */}
        <p className="mt-3 text-[15px] font-bold leading-snug text-gray-900 dark:text-white">
          {entry.hookText}
        </p>

        {/* Why it works panel */}
        <div className="mt-3 bg-gray-50 dark:bg-slate-700/50 rounded-lg p-3">
          <p className="text-[10px] font-bold uppercase tracking-wider text-gray-400 dark:text-slate-500 mb-1">
            Why it works
          </p>
          <p className="text-xs leading-relaxed text-gray-600 dark:text-slate-300">
            {entry.whyItWorks}
          </p>
        </div>

        {/* Footer: chips + views + link */}
        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${HOOK_CHIP_COLORS[entry.hookType] || "bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-slate-400"}`}>
            {entry.hookType}
          </span>
          <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${FORMAT_COLORS[entry.format] || "bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-slate-400"}`}>
            {entry.format}
          </span>
          <span className="rounded-full bg-gray-100 dark:bg-slate-700 px-2.5 py-0.5 text-[10px] font-semibold tabular-nums text-gray-500 dark:text-slate-400">
            {formatNum(entry.estimatedViews)} views
          </span>
          <a
            href={entry.url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto inline-flex items-center gap-1 rounded-lg border border-[#81D8D0] px-2.5 py-1 text-[10px] font-semibold text-[#81D8D0] transition hover:bg-[#81D8D0] hover:text-white dark:border-[#81D8D0]/60 dark:text-[#81D8D0] dark:hover:bg-[#81D8D0] dark:hover:text-white"
          >
            View
            <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
            </svg>
          </a>
        </div>

        {/* Tags */}
        {entry.tags.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1">
            {entry.tags.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-gray-100 dark:bg-slate-700 px-2 py-0.5 text-[10px] text-gray-500 dark:text-slate-400"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════ MAIN COMPONENT ══════════════════════ */

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

  /* Computed stats */
  const competitorCount = useMemo(() => (data ? data.entries.filter((e) => e.isCompetitor).length : 0), [data]);
  const avgViews = useMemo(() => {
    if (!data || data.entries.length === 0) return 0;
    return Math.round(data.entries.reduce((sum, e) => sum + e.estimatedViews, 0) / data.entries.length);
  }, [data]);
  const topHook = useMemo(() => {
    if (!data) return "-";
    const entries = Object.entries(data.byHookType);
    if (entries.length === 0) return "-";
    return entries.sort((a, b) => b[1] - a[1])[0][0];
  }, [data]);

  /* Hook type bar colors */
  const hookBarColors = useMemo(() => {
    const map: Record<string, string> = {};
    for (const [key, val] of Object.entries(HOOK_TYPE_COLORS)) {
      map[key] = val.bar;
    }
    return map;
  }, []);

  /* Loading */
  if (loading || !data) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 dark:border-slate-600 border-t-[#81D8D0]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Swipe File</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">Inspiration library &amp; competitive intelligence</p>
      </div>

      {/* KPI Metric Cards -- 3x2 grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <MetricCard label="Total Entries" value={data.totalEntries} subtitle="All saved entries" />
        <MetricCard label="Hook Types" value={hookTypes.length} subtitle="Unique hook types" />
        <MetricCard label="Formats" value={formats.length} subtitle="Content formats" />
        <MetricCard label="Competitor Entries" value={competitorCount} subtitle="Competitive intel" />
        <MetricCard label="Avg Views" value={avgViews} formatter={formatNum} subtitle="Across all entries" />
        <MetricCard label="Top Hook" value={0} subtitle={topHook} formatter={() => topHook} />
      </div>

      {/* Distribution Charts — side by side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <DistributionCard
          title="By Hook Type"
          data={data.byHookType}
          colorMap={hookBarColors}
        />
        <DistributionCard
          title="By Format"
          data={data.byFormat}
          colorMap={FORMAT_BAR_COLORS}
        />
      </div>

      {/* Filter Section */}
      <div className={cardCls}>
        <div className="flex flex-col gap-3">
          {/* Row 1: dropdowns + toggle + search */}
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">Filters</span>

            {/* Hook type dropdown */}
            <select
              value={hookFilter}
              onChange={(e) => setHookFilter(e.target.value)}
              className={selectCls}
            >
              <option value="all">All Hook Types</option>
              {Object.entries(data.byHookType).map(([type, count]) => (
                <option key={type} value={type}>{type} ({count})</option>
              ))}
            </select>

            {/* Format dropdown */}
            <select
              value={formatFilter}
              onChange={(e) => setFormatFilter(e.target.value)}
              className={selectCls}
            >
              <option value="all">All Formats</option>
              {formats.map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>

            {/* Competitor toggle */}
            <button
              onClick={() => setCompetitorOnly(!competitorOnly)}
              className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-all ${
                competitorOnly
                  ? "bg-red-600 text-white border-red-600 shadow-sm shadow-red-200 dark:shadow-red-900/30"
                  : "border-gray-300 text-gray-500 hover:bg-gray-50 dark:border-slate-600 dark:text-slate-400 dark:hover:bg-slate-700"
              }`}
            >
              Competitors{competitorOnly ? " ON" : ""}
            </button>

            {/* Search input */}
            <div className="relative flex-1 min-w-[160px] max-w-xs">
              <svg
                className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-400 dark:text-slate-500"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <input
                type="text"
                placeholder="Search tags..."
                value={tagSearch}
                onChange={(e) => setTagSearch(e.target.value)}
                className="w-full rounded-lg border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 pl-8 pr-3 py-1.5 text-xs text-gray-700 dark:text-slate-300 placeholder:text-gray-300 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-[#81D8D0]/50"
              />
            </div>

            {/* Sort buttons */}
            <div className="ml-auto flex items-center gap-1.5">
              <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400 dark:text-slate-500 mr-1">Sort</span>
              {(["views", "date", "hookType"] as SortKey[]).map((s) => (
                <button
                  key={s}
                  onClick={() => setSortBy(s)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                    sortBy === s
                      ? "bg-gray-800 dark:bg-slate-200 text-white dark:text-slate-900 shadow-sm"
                      : "bg-gray-100 dark:bg-slate-700 text-gray-500 dark:text-slate-400 hover:bg-gray-200 dark:hover:bg-slate-600"
                  }`}
                >
                  {s === "hookType" ? "Hook" : s === "views" ? "Views" : "Date"}
                </button>
              ))}
            </div>
          </div>

          {/* Results count */}
          <div className="flex items-center">
            <span className="text-xs text-gray-400 dark:text-gray-500">
              Showing {filtered.length} of {data.totalEntries} entries
            </span>
          </div>
        </div>
      </div>

      {/* Card Grid */}
      {filtered.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((entry) => (
            <SwipeCard key={entry.id} entry={entry} />
          ))}
        </div>
      ) : (
        /* Empty state */
        <div className="flex flex-col items-center justify-center py-20">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gray-100 dark:bg-slate-700">
            <svg className="h-8 w-8 text-gray-300 dark:text-slate-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
            </svg>
          </div>
          <p className="mt-4 text-sm font-semibold text-gray-500 dark:text-slate-400">No entries match your filters</p>
          <p className="mt-1 text-xs text-gray-400 dark:text-slate-500">Try broadening your search or removing some filters</p>
        </div>
      )}
    </div>
  );
}
