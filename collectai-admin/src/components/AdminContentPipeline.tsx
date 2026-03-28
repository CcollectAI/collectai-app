"use client";

import { useEffect, useState } from "react";
import { fetchPodPlannerData, PIPELINE_STAGES } from "@/lib/pod-planner";
import type { PodPlannerData, PipelineItem, PipelineStatus, Priority } from "@/lib/pod-planner";
import { AdminDemoBanner } from "@/components/AdminDemoBanner";

const PRIORITY_COLORS: Record<Priority, string> = {
  urgent: "border-l-red-500",
  high: "border-l-amber-500",
  normal: "border-l-gray-300",
  low: "border-l-gray-200",
};

const PRIORITY_BADGE: Record<Priority, string> = {
  urgent: "bg-red-100 text-red-700",
  high: "bg-amber-100 text-amber-700",
  normal: "hidden",
  low: "hidden",
};

function PipelineCard({ item }: { item: PipelineItem }) {
  const isOverdue = item.dueDate && item.dueDate < new Date().toISOString().slice(0, 10) && !["posted", "tracking"].includes(item.status);

  return (
    <div className={`rounded-lg border-l-4 bg-white p-3 shadow-sm transition hover:shadow-md ${PRIORITY_COLORS[item.priority]}`}>
      <p className="text-xs font-semibold text-[#0D1B2A] leading-tight">{item.title}</p>
      <p className="mt-1 text-[10px] text-gray-400 truncate">{item.description}</p>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {item.format && (
          <span className="rounded-full bg-gray-100 px-1.5 py-0.5 text-[9px] font-medium text-gray-500 capitalize">{item.format}</span>
        )}
        {item.conceptCluster && (
          <span className="rounded-full bg-blue-50 px-1.5 py-0.5 text-[9px] font-medium text-blue-600">{item.conceptCluster.replace(/-/g, " ")}</span>
        )}
        {item.priority !== "normal" && item.priority !== "low" && (
          <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase ${PRIORITY_BADGE[item.priority]}`}>{item.priority}</span>
        )}
      </div>

      <div className="mt-2 flex items-center justify-between">
        <span className="text-[10px] text-gray-400">{item.creatorName || "Unassigned"}</span>
        {item.dueDate && (
          <span className={`text-[10px] font-medium ${isOverdue ? "text-red-500" : "text-gray-400"}`}>
            {isOverdue ? "Overdue: " : ""}{item.dueDate}
          </span>
        )}
      </div>
    </div>
  );
}

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
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-[#FF6B6B]" />
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
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#0D1B2A]">Content Pipeline</h2>
          <AdminDemoBanner />
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        <div className="rounded-xl bg-white p-3 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400">Total Items</p>
          <p className="mt-0.5 text-2xl font-bold text-[#0D1B2A]">{stats.totalPipelineItems}</p>
        </div>
        <div className="rounded-xl bg-white p-3 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400">In Progress</p>
          <p className="mt-0.5 text-2xl font-bold text-blue-600">
            {stats.itemsByStatus.scripted + stats.itemsByStatus.filming + stats.itemsByStatus.editing}
          </p>
        </div>
        <div className="rounded-xl bg-white p-3 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400">Ready to Post</p>
          <p className="mt-0.5 text-2xl font-bold text-cyan-600">{stats.itemsByStatus.ready}</p>
        </div>
        <div className="rounded-xl bg-white p-3 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400">Posted</p>
          <p className="mt-0.5 text-2xl font-bold text-emerald-600">{stats.itemsByStatus.posted}</p>
        </div>
        <div className="rounded-xl bg-white p-3 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400">Tracking</p>
          <p className="mt-0.5 text-2xl font-bold text-rose-600">{stats.itemsByStatus.tracking}</p>
        </div>
        <div className="rounded-xl bg-white p-3 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400">Overdue</p>
          <p className={`mt-0.5 text-2xl font-bold ${stats.overdueItems > 0 ? "text-red-500" : "text-gray-300"}`}>{stats.overdueItems}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        <select
          value={filterPod}
          onChange={(e) => setFilterPod(e.target.value)}
          className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600"
        >
          <option value="all">All Pods</option>
          {pods.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <select
          value={filterCreator}
          onChange={(e) => setFilterCreator(e.target.value)}
          className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600"
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
          <div key={stage.id} className="w-52 flex-shrink-0">
            {/* Column header */}
            <div className="mb-2 flex items-center justify-between">
              <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase ${stage.color}`}>
                {stage.label}
              </span>
              <span className="text-xs font-bold tabular-nums text-gray-400">{columns[stage.id].length}</span>
            </div>

            {/* Cards */}
            <div className="space-y-2">
              {columns[stage.id].map((item) => (
                <PipelineCard key={item.id} item={item} />
              ))}
              {columns[stage.id].length === 0 && (
                <div className="rounded-lg border-2 border-dashed border-gray-200 p-4 text-center text-[10px] text-gray-300">
                  Empty
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
