"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchDemandSummary, DemandSummary } from "@/lib/collectai-api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

const STATUS_BADGE: Record<string, string> = {
  watching: "bg-blue-100 text-blue-700",
  candidate: "bg-amber-100 text-amber-700",
  promoted: "bg-green-100 text-green-700",
  rejected: "bg-gray-100 text-gray-500",
};

export function AdminDemandSignals() {
  const [data, setData] = useState<DemandSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const summary = await fetchDemandSummary();
      setData(summary);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load demand signals");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-400">
        Loading demand signals...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl bg-white p-6 shadow-sm">
        <p className="text-red-600">{error}</p>
        <button
          onClick={load}
          className="mt-3 rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  const dailyCounts = data.daily_request_counts ?? [];
  const last7 = dailyCounts.slice(-7);
  const maxCount = Math.max(...last7.map((d) => d.requests), 1);
  const dailyAvg =
    dailyCounts.length > 0
      ? Math.round(
          dailyCounts.reduce((sum, d) => sum + d.requests, 0) / dailyCounts.length
        )
      : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">Demand Signals</h2>
        <button
          onClick={load}
          className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
        >
          Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-2xl bg-white p-6 shadow-sm">
          <p className="text-sm text-gray-500">Pending Suggestions</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">
            {data.pending_suggestions}
          </p>
        </div>
        <div className="rounded-2xl bg-white p-6 shadow-sm">
          <p className="text-sm text-gray-500">Categories Watching</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">
            {data.new_categories_watching}
          </p>
        </div>
        <div className="rounded-2xl bg-white p-6 shadow-sm">
          <p className="text-sm text-gray-500">Daily Avg Requests</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{dailyAvg}</p>
        </div>
      </div>

      {/* Daily Trend */}
      {last7.length > 0 && (
        <div className="rounded-2xl bg-white dark:bg-slate-800 p-6 shadow-sm transition-colors">
          <h3 className="mb-4 text-sm font-medium text-gray-700 dark:text-gray-300">
            Daily Trend (Last 7 Days)
          </h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={last7.map(d => ({ date: d.day.slice(5), requests: d.requests, users: d.unique_users }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#9CA3AF" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#9CA3AF" }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: 8, border: "none", boxShadow: "0 2px 8px rgba(0,0,0,.12)", fontSize: 12 }} />
                <Bar dataKey="requests" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="users" fill="#81D8D0" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Top Requested Items */}
      <div className="rounded-2xl bg-white shadow-sm">
        <div className="border-b border-gray-100 px-6 py-4">
          <h3 className="text-sm font-medium text-gray-700">
            Top Requested Items
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-xs uppercase text-gray-400">
                <th className="px-6 py-3">Name</th>
                <th className="px-6 py-3">Category</th>
                <th className="px-6 py-3 text-right">Total Requests</th>
                <th className="px-6 py-3 text-right">Unique Users</th>
                <th className="px-6 py-3">Last Requested</th>
              </tr>
            </thead>
            <tbody>
              {(data.top_requested_items ?? []).map((item, i) => (
                <tr
                  key={i}
                  className="border-b border-gray-50 hover:bg-gray-50"
                >
                  <td className="px-6 py-3 font-medium text-gray-900">
                    {item.name}
                  </td>
                  <td className="px-6 py-3 text-gray-600">{item.suggested_category}</td>
                  <td className="px-6 py-3 text-right text-gray-900">
                    {item.total_requests}
                  </td>
                  <td className="px-6 py-3 text-right text-gray-600">
                    {item.unique_users}
                  </td>
                  <td className="px-6 py-3 text-gray-500">
                    {item.last_requested}
                  </td>
                </tr>
              ))}
              {(data.top_requested_items ?? []).length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-6 py-8 text-center text-gray-400"
                  >
                    No requested items yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Top Category Candidates */}
      <div className="rounded-2xl bg-white shadow-sm">
        <div className="border-b border-gray-100 px-6 py-4">
          <h3 className="text-sm font-medium text-gray-700">
            Top Category Candidates
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-xs uppercase text-gray-400">
                <th className="px-6 py-3">Name</th>
                <th className="px-6 py-3">Slug</th>
                <th className="px-6 py-3 text-right">Signal Count</th>
                <th className="px-6 py-3 text-right">Unique Users</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">First Seen</th>
                <th className="px-6 py-3">Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {(data.top_requested_categories ?? []).map((cat, i) => (
                <tr
                  key={i}
                  className="border-b border-gray-50 hover:bg-gray-50"
                >
                  <td className="px-6 py-3 font-medium text-gray-900">
                    {cat.name}
                  </td>
                  <td className="px-6 py-3 font-mono text-xs text-gray-500">
                    {cat.slug}
                  </td>
                  <td className="px-6 py-3 text-right text-gray-900">
                    {cat.signal_count}
                  </td>
                  <td className="px-6 py-3 text-right text-gray-600">
                    {cat.unique_users}
                  </td>
                  <td className="px-6 py-3">
                    <span
                      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_BADGE[cat.status] ?? "bg-gray-100 text-gray-500"}`}
                    >
                      {cat.status}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-gray-500">{cat.first_seen}</td>
                  <td className="px-6 py-3 text-gray-500">{cat.last_seen}</td>
                </tr>
              ))}
              {(data.top_requested_categories ?? []).length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-6 py-8 text-center text-gray-400"
                  >
                    No category candidates yet
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
