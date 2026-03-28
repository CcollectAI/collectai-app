"use client";

import { useState, useEffect, useCallback } from "react";
import {
  fetchSponsorAnalytics,
  type SponsoredEvent,
  type SponsorAnalyticsResponse,
} from "@/lib/collectai-api";

const TIER_BADGE: Record<string, string> = {
  gold: "bg-amber-100 text-amber-700",
  silver: "bg-gray-200 text-gray-600",
  bronze: "bg-orange-100 text-orange-800",
};

export function AdminSponsorAnalytics() {
  const [data, setData] = useState<SponsorAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSponsorAnalytics();
      setData(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load sponsor analytics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return <div className="flex items-center justify-center py-20 text-gray-400">Loading sponsor analytics...</div>;
  }

  if (error) {
    return (
      <div className="rounded-2xl bg-white p-6 shadow-sm">
        <p className="text-red-600">{error}</p>
        <button onClick={load} className="mt-3 rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200">Retry</button>
      </div>
    );
  }

  if (!data) return null;

  const events = data.sponsored_events;
  const totalImpressions = events.reduce((s, e) => s + e.impressions, 0);
  const totalClicks = events.reduce((s, e) => s + e.clicks, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">Sponsor Analytics</h2>
        <button onClick={load} className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200">Refresh</button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-2xl bg-white p-6 shadow-sm">
          <p className="text-sm text-gray-500">Total Sponsored Events</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{data.total}</p>
        </div>
        <div className="rounded-2xl bg-white p-6 shadow-sm">
          <p className="text-sm text-gray-500">Total Impressions</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{totalImpressions.toLocaleString()}</p>
        </div>
        <div className="rounded-2xl bg-white p-6 shadow-sm">
          <p className="text-sm text-gray-500">Total Clicks</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{totalClicks.toLocaleString()}</p>
        </div>
      </div>

      <div className="rounded-2xl bg-white shadow-sm">
        <div className="border-b border-gray-100 px-6 py-4">
          <h3 className="text-sm font-medium text-gray-700">Sponsored Events</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-xs uppercase text-gray-400">
                <th className="px-6 py-3">Title</th>
                <th className="px-6 py-3">Sponsor</th>
                <th className="px-6 py-3">Tier</th>
                <th className="px-6 py-3">Category</th>
                <th className="px-6 py-3">Paid At</th>
                <th className="px-6 py-3">Expires At</th>
                <th className="px-6 py-3 text-right">Impressions</th>
                <th className="px-6 py-3 text-right">Clicks</th>
                <th className="px-6 py-3 text-right">RSVPs</th>
              </tr>
            </thead>
            <tbody>
              {events.map((evt: SponsoredEvent, i: number) => (
                <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-6 py-3 font-medium text-gray-900">{evt.title}</td>
                  <td className="px-6 py-3 text-gray-600">{evt.sponsor_name}</td>
                  <td className="px-6 py-3">
                    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${TIER_BADGE[evt.sponsor_tier ?? ""] ?? "bg-gray-100 text-gray-500"}`}>
                      {evt.sponsor_tier ?? "—"}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-gray-600">{evt.category_id ?? "—"}</td>
                  <td className="px-6 py-3 text-gray-500">{evt.sponsor_paid_at ?? "—"}</td>
                  <td className="px-6 py-3 text-gray-500">{evt.sponsor_expires_at ?? "—"}</td>
                  <td className="px-6 py-3 text-right text-gray-900">{evt.impressions.toLocaleString()}</td>
                  <td className="px-6 py-3 text-right text-gray-900">{evt.clicks.toLocaleString()}</td>
                  <td className="px-6 py-3 text-right text-gray-600">{evt.rsvps}</td>
                </tr>
              ))}
              {events.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-6 py-8 text-center text-gray-400">No sponsored events yet</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
