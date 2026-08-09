"use client";

import { useEffect, useState } from "react";
import { fetchPodPlannerData, PIPELINE_STAGES } from "@/lib/pod-planner";
import type { PodPlannerData, Pod } from "@/lib/pod-planner";
import { AdminDemoBanner } from "@/components/AdminDemoBanner";

function PodCard({ pod }: { pod: Pod }) {
  const [expanded, setExpanded] = useState(false);
  const totalPipeline = Object.values(pod.pipelineCount).reduce((s, n) => s + n, 0);
  const progressPct = pod.targetVideosPerWeek > 0
    ? Math.min(100, Math.round((pod.videosThisWeek / pod.targetVideosPerWeek) * 100))
    : 0;

  return (
    <div className="rounded-2xl bg-white shadow-sm overflow-hidden">
      {/* Color bar */}
      <div className="h-1.5" style={{ backgroundColor: pod.color }} />

      <div className="p-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-[#0D1B2A]">{pod.name}</h3>
            <p className="text-xs text-gray-400">{pod.description}</p>
          </div>
          <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[10px] font-bold uppercase text-gray-500">
            {pod.language}
          </span>
        </div>

        {/* Weekly target progress */}
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-500">Weekly target</span>
            <span className="font-bold text-[#0D1B2A]">{pod.videosThisWeek}/{pod.targetVideosPerWeek}</span>
          </div>
          <div className="mt-1.5 h-2 rounded-full bg-gray-100 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${progressPct}%`,
                backgroundColor: progressPct >= 100 ? "#10B981" : progressPct >= 60 ? "#F59E0B" : "#EF4444",
              }}
            />
          </div>
        </div>

        {/* Stats grid */}
        <div className="mt-4 grid grid-cols-3 gap-3">
          <div>
            <p className="text-[10px] font-semibold text-gray-400">Members</p>
            <p className="text-lg font-bold text-[#0D1B2A]">{pod.members.length}</p>
          </div>
          <div>
            <p className="text-[10px] font-semibold text-gray-400">This Month</p>
            <p className="text-lg font-bold text-[#0D1B2A]">{pod.videosThisMonth}</p>
          </div>
          <div>
            <p className="text-[10px] font-semibold text-gray-400">Hit Rate</p>
            <p className={`text-lg font-bold ${pod.avgHitRate >= 20 ? "text-emerald-600" : pod.avgHitRate >= 10 ? "text-amber-600" : "text-gray-400"}`}>
              {pod.avgHitRate}%
            </p>
          </div>
        </div>

        {/* Pipeline mini-bar */}
        <div className="mt-4">
          <p className="text-[10px] font-semibold text-gray-400 mb-1.5">Pipeline ({totalPipeline})</p>
          <div className="flex h-4 rounded-full overflow-hidden bg-gray-100">
            {PIPELINE_STAGES.map((stage) => {
              const count = pod.pipelineCount[stage.id];
              if (count === 0) return null;
              const pct = (count / totalPipeline) * 100;
              return (
                <div
                  key={stage.id}
                  className={`${stage.color} flex items-center justify-center text-[8px] font-bold`}
                  style={{ width: `${pct}%` }}
                  title={`${stage.label}: ${count}`}
                >
                  {count > 0 && pct > 8 ? count : ""}
                </div>
              );
            })}
          </div>
        </div>

        {/* Revenue + Message Pod */}
        <div className="mt-4 flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2">
          <span className="text-xs text-gray-500">Revenue</span>
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-[#0D1B2A]">{"\u20AC"}{pod.totalRevenue}</span>
            <a
              href={`https://wa.me/?text=${encodeURIComponent(`Hi ${pod.name} team! 👋`)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-[10px] font-bold text-white transition hover:opacity-90 active:scale-95"
              style={{ backgroundColor: "#25D366" }}
              title={`Message ${pod.name} on WhatsApp`}
            >
              <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
              </svg>
              Message Pod
            </a>
          </div>
        </div>

        {/* Members toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-3 w-full text-center text-xs font-medium text-[#FF6B6B] transition hover:underline"
        >
          {expanded ? "Hide members" : `Show ${pod.members.length} member${pod.members.length === 1 ? "" : "s"}`}
        </button>

        {/* Members list */}
        {expanded && (
          <div className="mt-3 space-y-2">
            {pod.members.map((m) => (
              <div key={m.id} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2">
                <div className="flex items-center gap-1.5">
                  <div>
                    <div className="flex items-center gap-1">
                      <p className="text-xs font-semibold text-[#0D1B2A]">{m.name}</p>
                      <a
                        href={`https://wa.me/?text=${encodeURIComponent(`Hi ${m.name}!`)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={`Message ${m.name} on WhatsApp`}
                        className="inline-flex transition hover:opacity-80"
                      >
                        <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="#25D366">
                          <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                        </svg>
                      </a>
                    </div>
                    <p className="text-[10px] text-gray-400">{m.handle} · {m.platform}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xs font-bold text-[#0D1B2A]">{m.videosCount} videos</p>
                  <p className="text-[10px] text-gray-400">{m.hitRate}% hit rate</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function AdminPodManager() {
  const [data, setData] = useState<PodPlannerData | null>(null);
  const [loading, setLoading] = useState(true);

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

  const { pods, stats } = data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-bold text-[#0D1B2A]">Pod Management</h2>
        <AdminDemoBanner source="pods" />
      </div>

      {/* Global stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400">Active Pods</p>
          <p className="mt-1 text-2xl font-bold text-[#0D1B2A]">{stats.activePods}</p>
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400">Total Creators</p>
          <p className="mt-1 text-2xl font-bold text-[#0D1B2A]">{stats.totalCreators}</p>
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400">Videos This Week</p>
          <p className="mt-1 text-2xl font-bold text-emerald-600">{stats.videosThisWeek}</p>
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <p className="text-[10px] font-semibold uppercase text-gray-400">Videos This Month</p>
          <p className="mt-1 text-2xl font-bold text-[#0D1B2A]">{stats.videosThisMonth}</p>
        </div>
      </div>

      {/* Pod cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {pods.map((pod) => (
          <PodCard key={pod.id} pod={pod} />
        ))}
      </div>
    </div>
  );
}
