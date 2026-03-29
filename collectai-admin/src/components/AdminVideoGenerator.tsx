"use client";

// ═══════════════════════════════════════════════════════════════════════════
// Video Generator Tab — Remotion video pipeline integrated into UGC dashboard
// ═══════════════════════════════════════════════════════════════════════════

import { useState, useMemo } from "react";
import {
  TEMPLATES,
  NICHE_OPTIONS,
  fetchVideoScripts,
  fetchQueueStats,
  fetchAutomationRules,
  type VideoScript,
  type VideoTemplate,
  type TemplateId,
  type AutomationRule,
} from "@/lib/video-generator";
import { APP_CONFIG } from "../../admin.config";

// ─── Sub-views ───────────────────────────────────────────────────────────

type View = "generate" | "queue" | "performance" | "automation";

// ─── Main Component ──────────────────────────────────────────────────────

export function AdminVideoGenerator() {
  const [view, setView] = useState<View>("generate");
  const [scripts] = useState<VideoScript[]>(() => fetchVideoScripts());
  const stats = useMemo(() => fetchQueueStats(scripts), [scripts]);
  const [rules] = useState<AutomationRule[]>(() => fetchAutomationRules());

  const views: { id: View; label: string; icon: string }[] = [
    { id: "generate", label: "Generate", icon: "\u{1F3AC}" },
    { id: "queue", label: "Queue", icon: "\u{1F4CB}" },
    { id: "performance", label: "Performance", icon: "\u{1F4CA}" },
    { id: "automation", label: "Automation", icon: "\u{26A1}" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-bold text-gray-900 dark:text-white">
          Video Generator
        </h2>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Remotion-powered programmatic video pipeline — generate TikTok content at scale
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total Scripts" value={stats.totalScripts} color="text-gray-900 dark:text-white" />
        <StatCard label="Rendering" value={stats.byStatus["rendering"] ?? 0} color="text-amber-600" />
        <StatCard label="Ready to Post" value={stats.byStatus["rendered"] ?? 0} color="text-emerald-600" />
        <StatCard
          label="Est. Cost"
          value={`\u20AC${stats.estimatedCostTotal.toFixed(2)}`}
          color="text-[#81D8D0]"
        />
      </div>

      {/* View tabs */}
      <div className="flex gap-1 rounded-lg bg-gray-100 dark:bg-slate-700 p-1">
        {views.map((v) => (
          <button
            key={v.id}
            onClick={() => setView(v.id)}
            className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              view === v.id
                ? "bg-white dark:bg-slate-600 text-gray-900 dark:text-white shadow-sm"
                : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            }`}
          >
            {v.icon} {v.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {view === "generate" && <GenerateView />}
      {view === "queue" && <QueueView scripts={scripts} />}
      {view === "performance" && <PerformanceView scripts={scripts} />}
      {view === "automation" && <AutomationView rules={rules} />}
    </div>
  );
}

// ─── Generate View ───────────────────────────────────────────────────────

function GenerateView() {
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateId>("pull-reveal");
  const [selectedNiches, setSelectedNiches] = useState<string[]>(["pokemon"]);
  const [useSmart, setUseSmart] = useState(true);
  const [generated, setGenerated] = useState(false);

  const toggleNiche = (id: string) => {
    setSelectedNiches((prev) =>
      prev.includes(id) ? prev.filter((n) => n !== id) : [...prev, id],
    );
  };

  const selectAllNiches = () => {
    setSelectedNiches(
      selectedNiches.length === NICHE_OPTIONS.length ? [] : NICHE_OPTIONS.map((n) => n.id),
    );
  };

  const totalVideos = selectedNiches.length;
  const estimatedCost = totalVideos * 0.03;

  const handleGenerate = () => {
    setGenerated(true);
    setTimeout(() => setGenerated(false), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Template picker */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
          1. Choose Template
        </h3>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {TEMPLATES.map((t) => (
            <TemplateCard
              key={t.id}
              template={t}
              isSelected={selectedTemplate === t.id}
              onClick={() => setSelectedTemplate(t.id)}
            />
          ))}
        </div>
      </div>

      {/* Niche selector */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
            2. Select Categories
          </h3>
          <button
            onClick={selectAllNiches}
            className="text-xs text-[#81D8D0] hover:text-[#5FBFB6] font-medium"
          >
            {selectedNiches.length === NICHE_OPTIONS.length ? "Deselect All" : "Select All"}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {NICHE_OPTIONS.map((n) => (
            <button
              key={n.id}
              onClick={() => toggleNiche(n.id)}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium border transition-all ${
                selectedNiches.includes(n.id)
                  ? "border-[#81D8D0] bg-[#81D8D0]/10 text-[#5FBFB6]"
                  : "border-gray-200 dark:border-slate-600 text-gray-500 dark:text-gray-400 hover:border-gray-300"
              }`}
            >
              <span>{n.emoji}</span>
              <span>{n.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Options */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
          3. Options
        </h3>
        <div className="flex flex-wrap gap-4">
          <label className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
            <input
              type="checkbox"
              checked={useSmart}
              onChange={(e) => setUseSmart(e.target.checked)}
              className="rounded border-gray-300 text-[#81D8D0] focus:ring-[#81D8D0]"
            />
            Smart Mode (use learning system)
          </label>
        </div>
      </div>

      {/* Cost estimator + generate button */}
      <div className="flex items-center justify-between rounded-xl bg-gray-50 dark:bg-slate-700/50 p-4">
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {totalVideos} video{totalVideos !== 1 ? "s" : ""} &times; 1 template
          </p>
          <p className="text-sm font-semibold text-gray-900 dark:text-white">
            Estimated cost: <span className="text-[#81D8D0]">&euro;{estimatedCost.toFixed(2)}</span>
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={selectedNiches.length === 0 || generated}
          className={`rounded-lg px-6 py-2.5 text-sm font-semibold text-white transition-all ${
            generated
              ? "bg-emerald-500"
              : selectedNiches.length === 0
                ? "bg-gray-300 dark:bg-slate-600 cursor-not-allowed"
                : "bg-[#81D8D0] hover:bg-[#5FBFB6] shadow-sm"
          }`}
        >
          {generated ? "\u2713 Scripts Generated!" : "Generate Scripts"}
        </button>
      </div>

      {/* CLI hint */}
      <div className="rounded-lg border border-gray-200 dark:border-slate-600 bg-gray-50 dark:bg-slate-800 p-3">
        <p className="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-1.5">
          CLI equivalent
        </p>
        <code className="text-xs text-gray-600 dark:text-gray-300 font-mono break-all">
          cd video &amp;&amp; npx tsx scripts/generate.ts --template {selectedTemplate}{" "}
          --niche {selectedNiches[0] ?? "pokemon"}{" "}
          {useSmart ? "--smart " : ""}--lang EN
        </code>
      </div>
    </div>
  );
}

// ─── Queue View ──────────────────────────────────────────────────────────

function QueueView({ scripts }: { scripts: VideoScript[] }) {
  const statusStyles: Record<string, string> = {
    draft: "bg-gray-100 text-gray-600 dark:bg-slate-600 dark:text-gray-300",
    rendering: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    rendered: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400",
    posted: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
    tracking: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400",
  };

  const classStyles: Record<string, string> = {
    hit: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
    average: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    fail: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    pending: "bg-gray-100 text-gray-500 dark:bg-slate-600 dark:text-gray-400",
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
        Video Script Queue ({scripts.length})
      </h3>
      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-slate-700">
        <table className="w-full text-xs">
          <thead className="bg-gray-50 dark:bg-slate-700">
            <tr>
              <th className="px-3 py-2 text-left font-semibold text-gray-500 dark:text-gray-400">Template</th>
              <th className="px-3 py-2 text-left font-semibold text-gray-500 dark:text-gray-400">Niche</th>
              <th className="px-3 py-2 text-left font-semibold text-gray-500 dark:text-gray-400">Hook</th>
              <th className="px-3 py-2 text-left font-semibold text-gray-500 dark:text-gray-400">Status</th>
              <th className="px-3 py-2 text-right font-semibold text-gray-500 dark:text-gray-400">Views</th>
              <th className="px-3 py-2 text-right font-semibold text-gray-500 dark:text-gray-400">3s Ret.</th>
              <th className="px-3 py-2 text-left font-semibold text-gray-500 dark:text-gray-400">Class</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
            {scripts.map((s) => {
              const tmpl = TEMPLATES.find((t) => t.id === s.templateId);
              return (
                <tr key={s.id} className="hover:bg-gray-50 dark:hover:bg-slate-700/50 transition-colors">
                  <td className="px-3 py-2.5 font-medium text-gray-900 dark:text-white">
                    {tmpl?.icon} {tmpl?.label}
                  </td>
                  <td className="px-3 py-2.5 text-gray-600 dark:text-gray-300">{s.nicheLabel}</td>
                  <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400 max-w-[200px] truncate">
                    {s.hookText}
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${statusStyles[s.status] ?? ""}`}>
                      {s.status === "rendering" && (
                        <span className="mr-1 inline-block h-2 w-2 animate-spin rounded-full border border-amber-400 border-t-transparent" />
                      )}
                      {s.status}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-gray-600 dark:text-gray-300">
                    {s.views ? formatViews(s.views) : "\u2014"}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-gray-600 dark:text-gray-300">
                    {s.retention3s ? `${Math.round(s.retention3s * 100)}%` : "\u2014"}
                  </td>
                  <td className="px-3 py-2.5">
                    {s.classification ? (
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${classStyles[s.classification] ?? ""}`}>
                        {s.classification}
                      </span>
                    ) : (
                      <span className="text-gray-400">\u2014</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Performance View ────────────────────────────────────────────────────

function PerformanceView({ scripts }: { scripts: VideoScript[] }) {
  const tracked = scripts.filter((s) => s.classification && s.classification !== "pending");
  const hits = tracked.filter((s) => s.classification === "hit");
  const avgRetention = tracked.length > 0
    ? tracked.reduce((s, v) => s + (v.retention3s ?? 0), 0) / tracked.length
    : 0;
  const totalViews = tracked.reduce((s, v) => s + (v.views ?? 0), 0);

  // Template performance
  const templatePerf = TEMPLATES.map((t) => {
    const tScripts = tracked.filter((s) => s.templateId === t.id);
    const tHits = tScripts.filter((s) => s.classification === "hit").length;
    const tViews = tScripts.reduce((s, v) => s + (v.views ?? 0), 0);
    return {
      ...t,
      videos: tScripts.length,
      hits: tHits,
      hitRate: tScripts.length > 0 ? tHits / tScripts.length : 0,
      totalViews: tViews,
    };
  }).sort((a, b) => b.hitRate - a.hitRate);

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Videos Tracked" value={tracked.length} color="text-gray-900 dark:text-white" />
        <StatCard label="Hits" value={hits.length} color="text-emerald-600" />
        <StatCard label="Avg Retention" value={`${Math.round(avgRetention * 100)}%`} color="text-[#81D8D0]" />
        <StatCard label="Total Views" value={formatViews(totalViews)} color="text-blue-600" />
      </div>

      {/* Template breakdown */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
          Template Performance
        </h3>
        <div className="space-y-2">
          {templatePerf.map((t) => (
            <div key={t.id} className="flex items-center gap-3 rounded-lg border border-gray-200 dark:border-slate-700 p-3">
              <span className="text-xl">{t.icon}</span>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-gray-900 dark:text-white">{t.label}</p>
                <p className="text-[10px] text-gray-500 dark:text-gray-400">
                  {t.videos} videos &middot; {t.hits} hits &middot; {formatViews(t.totalViews)} views
                </p>
              </div>
              <div className="text-right">
                <p className={`text-sm font-bold ${t.hitRate >= 0.3 ? "text-emerald-600" : t.hitRate >= 0.1 ? "text-amber-600" : "text-gray-400"}`}>
                  {t.videos > 0 ? `${Math.round(t.hitRate * 100)}%` : "\u2014"}
                </p>
                <p className="text-[10px] text-gray-400">hit rate</p>
              </div>
              {/* Mini bar */}
              <div className="w-20 h-2 rounded-full bg-gray-100 dark:bg-slate-600 overflow-hidden">
                <div
                  className="h-full rounded-full bg-[#81D8D0]"
                  style={{ width: `${Math.round(t.hitRate * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Learning insights */}
      <div className="rounded-xl border border-[#81D8D0]/30 bg-[#81D8D0]/5 p-4">
        <h3 className="text-sm font-semibold text-[#5FBFB6] mb-2">
          Learning System Insights
        </h3>
        <ul className="space-y-1.5 text-xs text-gray-600 dark:text-gray-300">
          <li>&bull; &quot;Pull Reveal&quot; has highest retention across all niches (avg 52%) — suspense hooks outperform</li>
          <li>&bull; &quot;Hidden Gem&quot; drives 3.1x more app installs than other templates — QuickScan demo is key</li>
          <li>&bull; Hook &quot;hg-1&quot; (garage sale framing) has 55% est. retention — best single hook in library</li>
          <li>&bull; &quot;What&apos;s It Worth?&quot; + question hooks retain 14% better than statement hooks</li>
          <li>&bull; Recommendation: test &quot;Collection Flex&quot; for Sneakers — untested niche, high portfolio values</li>
          <li>&bull; A/B test running: &quot;pr-5&quot; vs &quot;pr-2&quot; for MTG — winner declared in 18h</li>
        </ul>
      </div>
    </div>
  );
}

// ─── Automation View ─────────────────────────────────────────────────────

function AutomationView({ rules }: { rules: AutomationRule[] }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
          Video Automation Rules
        </h3>
        <span className="text-[10px] text-gray-400 dark:text-gray-500">
          {rules.filter((r) => r.isActive).length}/{rules.length} active
        </span>
      </div>

      <div className="space-y-2">
        {rules.map((rule) => (
          <div
            key={rule.id}
            className={`rounded-xl border p-4 transition-all ${
              rule.isActive
                ? "border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800"
                : "border-gray-100 dark:border-slate-700/50 bg-gray-50 dark:bg-slate-800/50 opacity-60"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h4 className="text-xs font-semibold text-gray-900 dark:text-white">
                    {rule.name}
                  </h4>
                  <span className={`inline-flex rounded-full px-1.5 py-0.5 text-[9px] font-semibold ${
                    rule.isActive
                      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                      : "bg-gray-100 text-gray-500 dark:bg-slate-600 dark:text-gray-400"
                  }`}>
                    {rule.isActive ? "Active" : "Paused"}
                  </span>
                </div>
                <p className="text-[11px] text-gray-500 dark:text-gray-400 mb-2">
                  {rule.description}
                </p>
                <div className="flex flex-wrap gap-3 text-[10px]">
                  <span className="text-gray-400 dark:text-gray-500">
                    <strong className="text-gray-500 dark:text-gray-400">Trigger:</strong> {rule.trigger}
                  </span>
                  <span className="text-gray-400 dark:text-gray-500">
                    <strong className="text-gray-500 dark:text-gray-400">Action:</strong> {rule.action}
                  </span>
                </div>
              </div>
              <div className="text-right flex-shrink-0">
                <p className="text-lg font-bold text-gray-900 dark:text-white">
                  {rule.timesTriggered}
                </p>
                <p className="text-[10px] text-gray-400">triggered</p>
                {rule.lastTriggered && (
                  <p className="text-[10px] text-gray-400 mt-0.5">
                    Last: {new Date(rule.lastTriggered).toLocaleDateString()}
                  </p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Pipeline integration note */}
      <div className="rounded-lg border border-gray-200 dark:border-slate-600 bg-gray-50 dark:bg-slate-800 p-3">
        <p className="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-1">
          Pipeline Integration
        </p>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Generated videos automatically enter the Content Pipeline at &quot;scripted&quot; stage.
          Hit Replication creates new pipeline items tagged with the source video ID.
          Automation rules feed from UGC Analytics classifications and Demand Signals.
        </p>
      </div>
    </div>
  );
}

// ─── Shared Components ───────────────────────────────────────────────────

function StatCard({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-3">
      <p className="text-[10px] text-gray-400 dark:text-gray-500 mb-0.5">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

function TemplateCard({
  template,
  isSelected,
  onClick,
}: {
  template: VideoTemplate;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`text-left rounded-xl border-2 p-3 transition-all ${
        isSelected
          ? "border-[#81D8D0] bg-[#81D8D0]/5 shadow-sm"
          : "border-gray-200 dark:border-slate-700 hover:border-gray-300 dark:hover:border-slate-600"
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">{template.icon}</span>
        <span className="text-xs font-semibold text-gray-900 dark:text-white">
          {template.label}
        </span>
      </div>
      <p className="text-[10px] text-gray-500 dark:text-gray-400 mb-1.5">
        {template.description}
      </p>
      <div className="flex items-center gap-2 text-[9px] text-gray-400 dark:text-gray-500">
        <span>{template.avgDuration}</span>
        <span>&middot;</span>
        <span>{template.bestFor.slice(0, 40)}...</span>
      </div>
    </button>
  );
}

function formatViews(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}
