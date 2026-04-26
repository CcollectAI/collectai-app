"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchIntelSummary, IntelSummary, isUsingDemoData } from "@/lib/collectai-api";

const PILL = "rounded-full px-2 py-0.5 text-[11px] font-semibold";

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function fmtNum(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toLocaleString();
}

function fmtAge(iso: string | null | undefined): string {
  if (!iso) return "never";
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function AdminIntelligenceData() {
  const [data, setData] = useState<IntelSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(14);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await fetchIntelSummary(days);
      setData(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <div className="py-20 text-center text-gray-400">Loading intelligence data…</div>;
  if (error) return <div className="rounded-2xl bg-white p-6 text-red-600">{error}</div>;
  if (!data) return null;
  const demo = isUsingDemoData();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Demand-side intelligence</h2>
          <p className="mt-1 text-sm text-gray-500">
            Live aggregation of every demand signal captured across the app — searches, watchlists, paywall hits,
            affiliate clicks, vision-correction regret, and event engagement.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {demo && <span className={`${PILL} bg-amber-100 text-amber-800`}>demo data</span>}
          <select
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value, 10))}
            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm"
          >
            <option value={7}>7d</option>
            <option value={14}>14d</option>
            <option value={30}>30d</option>
            <option value={90}>90d</option>
          </select>
          <button onClick={load} className="rounded-lg bg-gray-100 px-4 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-200">
            Refresh
          </button>
        </div>
      </div>

      {/* Sources health snapshot */}
      <div className="rounded-2xl bg-white p-5 shadow-sm">
        <h3 className="mb-3 text-base font-semibold text-gray-900">Source freshness</h3>
        <p className="mb-3 text-xs text-gray-500">
          Row counts + last-write per demand-input table. If push tables stay at 0, FE wiring isn&apos;t firing.
        </p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {data.sources.map((s) => (
            <div key={s.source} className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
              <div className="font-mono text-[11px] text-gray-500">{s.source}</div>
              <div className="text-base font-semibold text-gray-900">{fmtNum(s.rows)}</div>
              <div className="text-[11px] text-gray-400">{fmtAge(s.latest)}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Top searches */}
        <div className="rounded-2xl bg-white p-5 shadow-sm">
          <h3 className="mb-1 text-base font-semibold text-gray-900">Top searches</h3>
          <p className="mb-3 text-xs text-gray-500">What users are looking for. High-volume queries with no catalog match are catalog-expansion candidates.</p>
          {data.top_searches.length === 0 ? (
            <div className="rounded-lg bg-gray-50 p-4 text-center text-sm text-gray-400">No searches yet</div>
          ) : (
            <div className="space-y-1">
              {data.top_searches.slice(0, 12).map((r, i) => (
                <div key={i} className="flex items-center justify-between rounded-md border border-gray-50 px-3 py-1.5 text-sm hover:bg-gray-50">
                  <div className="flex-1 truncate font-mono text-gray-700">&quot;{r.query}&quot;</div>
                  <div className="ml-3 flex items-center gap-2">
                    <span className={`${PILL} bg-gray-100 text-gray-600`}>{r.category}</span>
                    <span className="text-xs tabular-nums text-gray-500">{fmtNum(r.searches)} / {fmtNum(r.unique_users)}u</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* No-result searches — biggest catalog gap */}
        <div className="rounded-2xl bg-white p-5 shadow-sm">
          <h3 className="mb-1 text-base font-semibold text-gray-900">No-result searches <span className="ml-2 text-xs font-normal text-amber-600">catalog gaps</span></h3>
          <p className="mb-3 text-xs text-gray-500">Auto-feeds search_gap_worker into category_candidates. High-volume entries here = items to add to the catalog next.</p>
          {data.no_results_searches.length === 0 ? (
            <div className="rounded-lg bg-gray-50 p-4 text-center text-sm text-gray-400">No 0-result searches yet</div>
          ) : (
            <div className="space-y-1">
              {data.no_results_searches.slice(0, 12).map((r, i) => (
                <div key={i} className="flex items-center justify-between rounded-md border border-gray-50 px-3 py-1.5 text-sm hover:bg-gray-50">
                  <div className="flex-1 truncate font-mono text-gray-700">&quot;{r.query}&quot;</div>
                  <span className="text-xs tabular-nums text-gray-500">{fmtNum(r.searches)} / {fmtNum(r.unique_users)}u</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top watchlists */}
        <div className="rounded-2xl bg-white p-5 shadow-sm">
          <h3 className="mb-1 text-base font-semibold text-gray-900">Top watchlisted items</h3>
          <p className="mb-3 text-xs text-gray-500">Items most users are tracking. Reflects strong long-term demand even when a sale isn&apos;t imminent.</p>
          {data.top_watchlists.length === 0 ? (
            <div className="rounded-lg bg-gray-50 p-4 text-center text-sm text-gray-400">Nobody&apos;s watchlisted yet</div>
          ) : (
            <div className="space-y-1">
              {data.top_watchlists.slice(0, 10).map((r, i) => (
                <div key={i} className="flex items-center justify-between rounded-md border border-gray-50 px-3 py-1.5 text-sm hover:bg-gray-50">
                  <div className="flex-1 truncate text-gray-700">{r.title}</div>
                  <div className="ml-3 flex items-center gap-2">
                    <span className={`${PILL} bg-gray-100 text-gray-600`}>{r.category}</span>
                    <span className="text-xs tabular-nums text-gray-500">{fmtNum(r.unique_users)}u</span>
                    <span className="text-xs tabular-nums text-gray-400">{r.avg_target ? `~€${Math.round(r.avg_target)}` : ""}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top events by engagement */}
        <div className="rounded-2xl bg-white p-5 shadow-sm">
          <h3 className="mb-1 text-base font-semibold text-gray-900">Top events by engagement</h3>
          <p className="mb-3 text-xs text-gray-500">events.engagement_score = views + 5×follows + 10×RSVPs + 20×ticket_clicks. Updated every 30 min.</p>
          {data.top_events.length === 0 ? (
            <div className="rounded-lg bg-gray-50 p-4 text-center text-sm text-gray-400">No engaged events yet</div>
          ) : (
            <div className="space-y-1">
              {data.top_events.slice(0, 10).map((r) => (
                <div key={r.event_id} className="flex items-center justify-between rounded-md border border-gray-50 px-3 py-1.5 text-sm hover:bg-gray-50">
                  <div className="flex-1 truncate text-gray-700">{r.title || r.event_id.slice(0, 8)}</div>
                  <div className="ml-3 flex items-center gap-2">
                    {r.category_id && <span className={`${PILL} bg-gray-100 text-gray-600`}>{r.category_id}</span>}
                    <span className="text-xs font-semibold tabular-nums text-amber-700">{fmtNum(r.engagement_score)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top regret categories */}
        <div className="rounded-2xl bg-white p-5 shadow-sm">
          <h3 className="mb-1 text-base font-semibold text-gray-900">Vision regret rate by category <span className="ml-2 text-xs font-normal text-red-600">model error</span></h3>
          <p className="mb-3 text-xs text-gray-500">% of AI/scan-added items deleted or archived within 7 days. High = vision is misclassifying that category. Multiplied into scan_correction weight on next retrain.</p>
          {data.top_regret_categories.length === 0 ? (
            <div className="rounded-lg bg-gray-50 p-4 text-center text-sm text-gray-400">Not enough data yet (≥10 items per cat needed)</div>
          ) : (
            <div className="space-y-1">
              {data.top_regret_categories.slice(0, 12).map((r) => (
                <div key={r.category} className="flex items-center justify-between rounded-md border border-gray-50 px-3 py-1.5 text-sm hover:bg-gray-50">
                  <div className="flex-1 truncate text-gray-700">{r.category}</div>
                  <div className="ml-3 flex items-center gap-3">
                    <span className={`text-xs font-semibold tabular-nums ${(r.regret_rate_30d ?? 0) > 0.15 ? "text-red-600" : "text-gray-500"}`}>{fmtPct(r.regret_rate_30d)}</span>
                    <span className="text-xs tabular-nums text-gray-400">{fmtNum(r.items_regretted)}/{fmtNum(r.items_added)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top affiliates */}
        <div className="rounded-2xl bg-white p-5 shadow-sm">
          <h3 className="mb-1 text-base font-semibold text-gray-900">Top affiliate clicks</h3>
          <p className="mb-3 text-xs text-gray-500">Which marketplace + category combinations users actually tap. Highest revenue-conversion hint pre-launch.</p>
          {data.top_affiliates.length === 0 ? (
            <div className="rounded-lg bg-gray-50 p-4 text-center text-sm text-gray-400">No affiliate clicks yet</div>
          ) : (
            <div className="space-y-1">
              {data.top_affiliates.slice(0, 12).map((r, i) => (
                <div key={i} className="flex items-center justify-between rounded-md border border-gray-50 px-3 py-1.5 text-sm hover:bg-gray-50">
                  <div className="flex items-center gap-2 truncate">
                    <span className={`${PILL} bg-gray-100 text-gray-600`}>{r.source}</span>
                    <span className="text-gray-500">{r.category}</span>
                  </div>
                  <span className="text-xs tabular-nums text-gray-500">{fmtNum(r.clicks)} / {fmtNum(r.unique_users)}u</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top paywall rejections */}
        <div className="rounded-2xl bg-white p-5 shadow-sm lg:col-span-2">
          <h3 className="mb-1 text-base font-semibold text-gray-900">Paywall rejections by feature</h3>
          <p className="mb-3 text-xs text-gray-500">Where free users hit Pro gates. High dismissal rate = either pricing issue or low-value feature behind the wall. Compare views vs dismissals to spot conversion problems.</p>
          {data.top_paywall_rejections.length === 0 ? (
            <div className="rounded-lg bg-gray-50 p-4 text-center text-sm text-gray-400">No paywall events yet</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-xs text-gray-500">
                <tr>
                  <th className="px-2 py-1 text-left">Feature</th>
                  <th className="px-2 py-1 text-right">Views</th>
                  <th className="px-2 py-1 text-right">Dismissals</th>
                  <th className="px-2 py-1 text-right">Dismiss rate</th>
                  <th className="px-2 py-1 text-right">Unique users</th>
                </tr>
              </thead>
              <tbody>
                {data.top_paywall_rejections.map((r) => {
                  const rate = r.views > 0 ? r.dismissals / r.views : 0;
                  return (
                    <tr key={r.feature} className="border-t border-gray-50">
                      <td className="px-2 py-1 font-mono text-gray-700">{r.feature}</td>
                      <td className="px-2 py-1 text-right tabular-nums">{fmtNum(r.views)}</td>
                      <td className="px-2 py-1 text-right tabular-nums">{fmtNum(r.dismissals)}</td>
                      <td className={`px-2 py-1 text-right font-semibold tabular-nums ${rate > 0.7 ? "text-red-600" : rate > 0.5 ? "text-amber-600" : "text-gray-500"}`}>
                        {fmtPct(rate)}
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums text-gray-500">{fmtNum(r.unique_users)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
