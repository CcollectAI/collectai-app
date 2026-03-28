"use client";

import { useEffect, useState } from "react";
import { fetchPodPlannerData, PIPELINE_STAGES } from "@/lib/pod-planner";
import type { PodPlannerData, PipelineItem, PipelineStatus, Priority } from "@/lib/pod-planner";
import { AdminDemoBanner } from "@/components/AdminDemoBanner";

// ─── Stage accent colors (top border on columns) ────────────────────────────

const STAGE_ACCENT: Record<PipelineStatus, string> = {
  idea: "border-t-gray-400",
  scripted: "border-t-blue-500",
  filming: "border-t-purple-500",
  editing: "border-t-amber-500",
  ready: "border-t-cyan-500",
  posted: "border-t-emerald-500",
  tracking: "border-t-rose-500",
};

const STAGE_BAR_COLOR: Record<PipelineStatus, string> = {
  idea: "bg-gray-400",
  scripted: "bg-blue-500",
  filming: "bg-purple-500",
  editing: "bg-amber-500",
  ready: "bg-cyan-500",
  posted: "bg-emerald-500",
  tracking: "bg-rose-500",
};

const STAGE_COUNT_PILL: Record<PipelineStatus, string> = {
  idea: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300",
  scripted: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  filming: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  editing: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  ready: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300",
  posted: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  tracking: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
};

// ─── Priority top-accent colors (card top line) ─────────────────────────────

const PRIORITY_ACCENT: Record<Priority, string> = {
  urgent: "bg-red-500",
  high: "bg-amber-500",
  normal: "bg-gray-200 dark:bg-slate-600",
  low: "bg-gray-100 dark:bg-slate-700",
};

const PRIORITY_FLAG: Record<Priority, { label: string; cls: string } | null> = {
  urgent: { label: "URGENT", cls: "bg-red-500 text-white" },
  high: { label: "HIGH", cls: "bg-amber-500 text-white" },
  normal: null,
  low: null,
};

// ─── Icons (inline SVG) ─────────────────────────────────────────────────────

function UserIcon() {
  return (
    <svg className="h-3 w-3 text-gray-400 dark:text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  );
}

function ClockIcon({ overdue }: { overdue: boolean }) {
  return (
    <svg className={`h-3 w-3 ${overdue ? "text-red-500" : "text-gray-400 dark:text-gray-500"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg className="h-5 w-5 text-gray-300 dark:text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
    </svg>
  );
}

// ─── Pipeline Card ──────────────────────────────────────────────────────────

function PipelineCard({ item }: { item: PipelineItem }) {
  const isOverdue =
    item.dueDate &&
    item.dueDate < new Date().toISOString().slice(0, 10) &&
    !["posted", "tracking"].includes(item.status);

  const flag = PRIORITY_FLAG[item.priority];

  return (
    <div className="relative bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700 p-3 transition hover:shadow-md">
      {/* Top accent line */}
      <div className={`absolute top-0 left-0 right-0 h-[2px] rounded-t-xl ${PRIORITY_ACCENT[item.priority]}`} />

      {/* Priority flag — top-right corner */}
      {flag && (
        <span className={`absolute -top-1.5 right-2 rounded-b px-1.5 py-0.5 text-[8px] font-bold tracking-wider ${flag.cls}`}>
          {flag.label}
        </span>
      )}

      {/* Title */}
      <p className="text-sm font-semibold text-gray-900 dark:text-white leading-tight pr-10">
        {item.title}
      </p>

      {/* Description */}
      {item.description && (
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400 line-clamp-2">
          {item.description}
        </p>
      )}

      {/* Badges row */}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {item.format && (
          <span className="rounded-full bg-gray-100 dark:bg-slate-700 px-2 py-0.5 text-[10px] font-medium text-gray-500 dark:text-gray-400 capitalize">
            {item.format}
          </span>
        )}
        {item.conceptCluster && (
          <span className="rounded-full bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 text-[10px] font-medium text-blue-600 dark:text-blue-400">
            {item.conceptCluster.replace(/-/g, " ")}
          </span>
        )}
      </div>

      {/* Footer */}
      <div className="mt-2.5 flex items-center justify-between">
        <span className="flex items-center gap-1 text-[10px] text-gray-400 dark:text-gray-500">
          <UserIcon />
          {item.creatorName || "Unassigned"}
        </span>
        {item.dueDate && (
          <span className={`flex items-center gap-1 text-[10px] font-medium ${isOverdue ? "text-red-500" : "text-gray-400 dark:text-gray-500"}`}>
            <ClockIcon overdue={!!isOverdue} />
            {item.dueDate}
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Progress Bar (stacked horizontal) ──────────────────────────────────────

function StageProgressBar({ columns, total }: { columns: Record<PipelineStatus, PipelineItem[]>; total: number }) {
  if (total === 0) return null;

  return (
    <div className="flex items-center gap-2">
      <div className="flex h-2.5 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-slate-700">
        {PIPELINE_STAGES.map((stage) => {
          const pct = (columns[stage.id].length / total) * 100;
          if (pct === 0) return null;
          return (
            <div
              key={stage.id}
              className={`${STAGE_BAR_COLOR[stage.id]} transition-all duration-300`}
              style={{ width: `${pct}%` }}
              title={`${stage.label}: ${columns[stage.id].length} (${Math.round(pct)}%)`}
            />
          );
        })}
      </div>
      <div className="flex gap-2">
        {PIPELINE_STAGES.map((stage) =>
          columns[stage.id].length > 0 ? (
            <span key={stage.id} className="flex items-center gap-1 text-[10px] text-gray-400 dark:text-gray-500">
              <span className={`inline-block h-2 w-2 rounded-full ${STAGE_BAR_COLOR[stage.id]}`} />
              {stage.label}
            </span>
          ) : null
        )}
      </div>
    </div>
  );
}

// ─── Main Component ─────────────────────────────────────────────────────────

export function AdminContentPipeline() {
  const [data, setData] = useState<PodPlannerData | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterPod, setFilterPod] = useState<string>("all");
  const [filterCreator, setFilterCreator] = useState<string>("all");

  useEffect(() => {
    setLoading(true);
    fetchPodPlannerData().then((d) => {
      setData(d);
      setLoading(false);
    });
  }, []);

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 dark:border-slate-600 border-t-[#FF6B6B]" />
      </div>
    );
  }

  const { pipeline, pods, stats } = data;

  // Apply filters
  const filtered = pipeline.filter((item) => {
    if (filterPod !== "all" && item.podId !== filterPod) return false;
    if (filterCreator !== "all" && item.creatorId !== filterCreator) return false;
    return true;
  });

  // Group by status
  const columns: Record<PipelineStatus, PipelineItem[]> = {
    idea: [], scripted: [], filming: [], editing: [], ready: [], posted: [], tracking: [],
  };
  for (const item of filtered) {
    columns[item.status].push(item);
  }

  // Unique creators for filter
  const creators = [...new Map(pipeline.map((p) => [p.creatorId, { id: p.creatorId, name: p.creatorName }])).values()].filter((c) => c.name);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#0D1B2A] dark:text-white">Content Pipeline</h2>
          <AdminDemoBanner />
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        <div className="rounded-xl bg-white dark:bg-slate-800 p-3 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400 dark:text-gray-500">Total Items</p>
          <p className="mt-0.5 text-2xl font-bold text-[#0D1B2A] dark:text-white">{stats.totalPipelineItems}</p>
        </div>
        <div className="rounded-xl bg-white dark:bg-slate-800 p-3 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400 dark:text-gray-500">In Progress</p>
          <p className="mt-0.5 text-2xl font-bold text-blue-600 dark:text-blue-400">
            {stats.itemsByStatus.scripted + stats.itemsByStatus.filming + stats.itemsByStatus.editing}
          </p>
        </div>
        <div className="rounded-xl bg-white dark:bg-slate-800 p-3 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400 dark:text-gray-500">Ready to Post</p>
          <p className="mt-0.5 text-2xl font-bold text-cyan-600 dark:text-cyan-400">{stats.itemsByStatus.ready}</p>
        </div>
        <div className="rounded-xl bg-white dark:bg-slate-800 p-3 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400 dark:text-gray-500">Posted</p>
          <p className="mt-0.5 text-2xl font-bold text-emerald-600 dark:text-emerald-400">{stats.itemsByStatus.posted}</p>
        </div>
        <div className="rounded-xl bg-white dark:bg-slate-800 p-3 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400 dark:text-gray-500">Tracking</p>
          <p className="mt-0.5 text-2xl font-bold text-rose-600 dark:text-rose-400">{stats.itemsByStatus.tracking}</p>
        </div>
        <div className="rounded-xl bg-white dark:bg-slate-800 p-3 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400 dark:text-gray-500">Overdue</p>
          <p className={`mt-0.5 text-2xl font-bold ${stats.overdueItems > 0 ? "text-red-500" : "text-gray-300 dark:text-slate-600"}`}>
            {stats.overdueItems}
          </p>
        </div>
      </div>

      {/* Stage progress bar */}
      <StageProgressBar columns={columns} total={filtered.length} />

      {/* Filters */}
      <div className="flex gap-2">
        <select
          value={filterPod}
          onChange={(e) => setFilterPod(e.target.value)}
          className="rounded-lg border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-300"
        >
          <option value="all">All Pods</option>
          {pods.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <select
          value={filterCreator}
          onChange={(e) => setFilterCreator(e.target.value)}
          className="rounded-lg border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-300"
        >
          <option value="all">All Creators</option>
          {creators.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>

      {/* Kanban board */}
      <div className="flex gap-3 overflow-x-auto pb-4">
        {PIPELINE_STAGES.map((stage) => (
          <div
            key={stage.id}
            className={`w-56 flex-shrink-0 bg-gray-50/50 dark:bg-slate-800/50 rounded-xl p-2 border-t-[3px] ${STAGE_ACCENT[stage.id]} min-h-[200px]`}
          >
            {/* Column header */}
            <div className="mb-2.5 flex items-center justify-between px-1">
              <span className="text-xs font-bold text-gray-700 dark:text-gray-200">
                {stage.label}
              </span>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold tabular-nums ${STAGE_COUNT_PILL[stage.id]}`}>
                {columns[stage.id].length}
              </span>
            </div>

            {/* Cards */}
            <div className="space-y-2">
              {columns[stage.id].map((item) => (
                <PipelineCard key={item.id} item={item} />
              ))}

              {/* Empty column placeholder */}
              {columns[stage.id].length === 0 && (
                <div className="border-2 border-dashed border-gray-200 dark:border-slate-600 rounded-xl flex flex-col items-center justify-center min-h-[80px] gap-1">
                  <PlusIcon />
                  <span className="text-[10px] text-gray-300 dark:text-slate-500">No items</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
