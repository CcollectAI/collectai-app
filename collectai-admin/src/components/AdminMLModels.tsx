"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchModels,
  fetchMetrics,
  activateBest,
  reloadCategory,
  trainNow,
} from "@/lib/collectai-api";
import type { ModelRow, MaeRow, CountsRow } from "@/lib/collectai-api";

export function AdminMLModels() {
  const [models, setModels] = useState<ModelRow[]>([]);
  const [mae, setMae] = useState<MaeRow[]>([]);
  const [counts, setCounts] = useState<CountsRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [m, met] = await Promise.all([fetchModels(), fetchMetrics()]);
      setModels(m);
      setMae(met.mae);
      setCounts(met.counts_7d);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Derive unique categories from models + metrics
  const categories = Array.from(
    new Set([
      ...models.map((m) => m.category),
      ...mae.map((m) => m.category),
      ...counts.map((c) => c.category),
    ])
  ).sort();

  // Helpers
  const maeForCategory = (cat: string): number | null => {
    const row = mae.find((m) => m.category === cat);
    return row?.mae ?? null;
  };

  const countForCategory = (cat: string): number => {
    return counts
      .filter((c) => c.category === cat)
      .reduce((sum, c) => sum + c.n, 0);
  };

  const activeModelForCategory = (cat: string): ModelRow | undefined => {
    return models.find((m) => m.category === cat && m.status === "active");
  };

  // Actions
  const handleAction = async (label: string, fn: () => Promise<unknown>) => {
    setStatus(`Running: ${label}...`);
    try {
      await fn();
      setStatus(`Done: ${label}`);
      await load();
    } catch (err) {
      setStatus(
        `Error (${label}): ${err instanceof Error ? err.message : "unknown"}`
      );
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-gray-500 text-sm">Loading ML models...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-2xl p-6">
        <p className="text-red-800 font-medium">Failed to load ML data</p>
        <p className="text-red-600 text-sm mt-1">{error}</p>
        <button
          onClick={load}
          className="mt-3 rounded-lg px-3 py-1.5 bg-red-600 text-white text-sm hover:bg-red-700"
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
        <h2 className="text-xl font-bold text-gray-900">ML Model Monitor</h2>
        <button
          onClick={load}
          className="rounded-lg px-3 py-1.5 bg-gray-200 text-gray-700 text-sm hover:bg-gray-300"
        >
          Refresh
        </button>
      </div>

      {/* Status banner */}
      {status && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
          <p className="text-sm text-amber-800">{status}</p>
        </div>
      )}

      {/* Actions bar */}
      <div className="bg-white rounded-2xl shadow-sm p-4">
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => handleAction("Retrain All", () => trainNow())}
            className="rounded-lg px-3 py-1.5 bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700"
          >
            Retrain All
          </button>
          <span className="text-gray-300 mx-1">|</span>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() =>
                handleAction(`Train ${cat}`, () => trainNow(cat))
              }
              className="rounded-lg px-3 py-1.5 bg-gray-200 text-gray-700 text-sm hover:bg-gray-300"
            >
              Train {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Active Models table */}
      <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-700">
            Active Models
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="px-4 py-2 text-left font-semibold text-gray-600">
                  Category
                </th>
                <th className="px-4 py-2 text-left font-semibold text-gray-600">
                  Version
                </th>
                <th className="px-4 py-2 text-right font-semibold text-gray-600">
                  MAE
                </th>
                <th className="px-4 py-2 text-right font-semibold text-gray-600">
                  7d Prediction Count
                </th>
                <th className="px-4 py-2 text-right font-semibold text-gray-600">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {categories.map((cat) => {
                const active = activeModelForCategory(cat);
                const catMae = maeForCategory(cat);
                const catCount = countForCategory(cat);
                return (
                  <tr key={cat} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium text-gray-900">
                      {cat}
                    </td>
                    <td className="px-4 py-2 text-gray-600">
                      {active ? (
                        <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">
                          {active.version}
                        </code>
                      ) : (
                        <span className="text-gray-400">--</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right text-gray-700">
                      {catMae !== null ? catMae.toFixed(2) : "--"}
                    </td>
                    <td className="px-4 py-2 text-right text-gray-700">
                      {catCount.toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() =>
                            handleAction(
                              `Reload ${cat}`,
                              () => reloadCategory(cat)
                            )
                          }
                          className="rounded-lg px-3 py-1.5 bg-gray-200 text-gray-700 text-xs hover:bg-gray-300"
                        >
                          Reload Cache
                        </button>
                        <button
                          onClick={() =>
                            handleAction(
                              `Activate best ${cat}`,
                              () => activateBest(cat)
                            )
                          }
                          className="rounded-lg px-3 py-1.5 bg-indigo-600 text-white text-xs hover:bg-indigo-700"
                        >
                          Activate Best
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {categories.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-gray-400">
                    No models found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* MAE Leaderboard table */}
      <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-700">
            MAE Leaderboard
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="px-4 py-2 text-left font-semibold text-gray-600">
                  Category
                </th>
                <th className="px-4 py-2 text-left font-semibold text-gray-600">
                  Version
                </th>
                <th className="px-4 py-2 text-right font-semibold text-gray-600">
                  MAE
                </th>
                <th className="px-4 py-2 text-right font-semibold text-gray-600">
                  Samples
                </th>
              </tr>
            </thead>
            <tbody>
              {[...mae]
                .filter((r) => r.mae !== null)
                .sort((a, b) => (a.mae ?? Infinity) - (b.mae ?? Infinity))
                .map((row, i) => (
                  <tr
                    key={`${row.category}-${row.model_version}-${i}`}
                    className="border-t border-gray-100 hover:bg-gray-50"
                  >
                    <td className="px-4 py-2 font-medium text-gray-900">
                      {row.category}
                    </td>
                    <td className="px-4 py-2 text-gray-600">
                      <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">
                        {row.model_version}
                      </code>
                    </td>
                    <td className="px-4 py-2 text-right text-gray-700">
                      {row.mae !== null ? row.mae.toFixed(2) : "--"}
                    </td>
                    <td className="px-4 py-2 text-right text-gray-700">
                      {row.n.toLocaleString()}
                    </td>
                  </tr>
                ))}
              {mae.filter((r) => r.mae !== null).length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-gray-400">
                    No MAE data available
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
