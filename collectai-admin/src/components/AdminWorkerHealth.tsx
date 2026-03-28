"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchWorkerHealth, type WorkerStatus } from "@/lib/collectai-api";

const STATUS_ORDER: Record<WorkerStatus["status"], number> = {
  overdue: 0,
  never_run: 1,
  ok: 2,
  on_demand: 3,
};

const STATUS_BADGE: Record<WorkerStatus["status"], string> = {
  ok: "bg-emerald-100 text-emerald-700",
  overdue: "bg-red-100 text-red-700",
  never_run: "bg-amber-100 text-amber-700",
  on_demand: "bg-blue-100 text-blue-700",
};

function relativeTime(iso: string | null): string {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 0) return "Just now";
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatDuration(seconds: number): string {
  if (seconds < 1) return "<1s";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  return `${Math.round(seconds / 60)}m`;
}

export function AdminWorkerHealth() {
  const [workers, setWorkers] = useState<WorkerStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const data = await fetchWorkerHealth();
      const sorted = [...data].sort(
        (a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status]
      );
      setWorkers(sorted);
      setLastRefresh(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch worker health");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 60_000);
    return () => clearInterval(interval);
  }, [refresh]);

  const okCount = workers.filter((w) => w.status === "ok").length;
  const overdueCount = workers.filter((w) => w.status === "overdue").length;
  const neverRunCount = workers.filter((w) => w.status === "never_run").length;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-500">
        <svg
          className="animate-spin h-5 w-5 mr-2 text-gray-400"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
        Loading worker health...
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center">
        <p className="text-red-700 font-medium mb-2">Error loading worker health</p>
        <p className="text-red-500 text-sm mb-4">{error}</p>
        <button
          onClick={refresh}
          className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900">Worker Health</h2>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-xs text-gray-400 flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              Auto-refresh 60s &middot; Updated {relativeTime(lastRefresh.toISOString())}
            </span>
          )}
          <button
            onClick={refresh}
            className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl shadow-sm p-4">
          <p className="text-sm text-gray-500">Total Workers</p>
          <p className="text-3xl font-bold text-gray-900">{workers.length}</p>
        </div>
        <div className="bg-white rounded-2xl shadow-sm p-4">
          <p className="text-sm text-gray-500">OK</p>
          <p className="text-3xl font-bold text-emerald-600">{okCount}</p>
        </div>
        <div className="bg-white rounded-2xl shadow-sm p-4">
          <p className="text-sm text-gray-500">Overdue</p>
          <p className="text-3xl font-bold text-red-600">{overdueCount}</p>
        </div>
        <div className="bg-white rounded-2xl shadow-sm p-4">
          <p className="text-sm text-gray-500">Never Run</p>
          <p className="text-3xl font-bold text-amber-600">{neverRunCount}</p>
        </div>
      </div>

      {/* Worker Table */}
      <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-gray-500">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Last Run</th>
                <th className="px-4 py-3 font-medium text-right">Run Count</th>
                <th className="px-4 py-3 font-medium text-right">Avg Duration</th>
                <th className="px-4 py-3 font-medium text-right">Expected Interval</th>
                <th className="px-4 py-3 font-medium text-right">Minutes Overdue</th>
              </tr>
            </thead>
            <tbody>
              {workers.map((w) => (
                <tr
                  key={w.name}
                  className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-gray-900">{w.name}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[w.status]}`}
                    >
                      {w.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{relativeTime(w.last_run_at)}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{w.run_count.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{formatDuration(w.average_duration_s)}</td>
                  <td className="px-4 py-3 text-right text-gray-600">
                    {w.expected_interval_minutes > 0 ? `${w.expected_interval_minutes}m` : "\u2014"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {w.minutes_overdue > 0 ? (
                      <span className="text-red-600 font-medium">{Math.round(w.minutes_overdue)}m</span>
                    ) : (
                      <span className="text-gray-400">&mdash;</span>
                    )}
                  </td>
                </tr>
              ))}
              {workers.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                    No workers found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
