"use client";

import { useState, useEffect, useCallback } from "react";
import { APP_CONFIG } from "../../admin.config";

interface ProviderSpend {
  provider: string;
  spent_eur: number;
  calls: number;
  cost_per_call: number;
  paused: boolean;
}

interface SpendSummary {
  month: string;
  budget_eur: number;
  total_spent_eur: number;
  remaining_eur: number;
  pct_used: number;
  budget_breached: boolean;
  providers: ProviderSpend[];
  recent_calls: { provider: string; cost_eur: number; timestamp: string; running_total: number }[];
}

const API = APP_CONFIG.api.baseUrl;
const headers: Record<string, string> = {
  "X-Ops-Key": APP_CONFIG.api.opsKey,
  "Content-Type": "application/json",
};

export function AdminSpendMonitor() {
  const [data, setData] = useState<SpendSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [budgetInput, setBudgetInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API}/admin/spend-summary`, { headers });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setBudgetInput(String(json.budget_eur));
      setError("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to fetch spend data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  const updateBudget = async () => {
    const val = parseFloat(budgetInput);
    if (isNaN(val) || val < 0) return;
    setSaving(true);
    try {
      await fetch(`${API}/admin/spend-budget`, {
        method: "POST",
        headers,
        body: JSON.stringify({ budget_eur: val }),
      });
      showToast(`Budget updated to \u20ac${val}`);
      fetchData();
    } catch {
      showToast("Failed to update budget");
    } finally {
      setSaving(false);
    }
  };

  const togglePause = async (provider: string, currentlyPaused: boolean) => {
    try {
      await fetch(`${API}/admin/spend-pause`, {
        method: "POST",
        headers,
        body: JSON.stringify({ provider, paused: !currentlyPaused }),
      });
      showToast(`${provider} ${!currentlyPaused ? "paused" : "resumed"}`);
      fetchData();
    } catch {
      showToast("Failed to toggle provider");
    }
  };

  const resetCounters = async () => {
    if (!confirm("Reset all spend counters? This cannot be undone.")) return;
    try {
      await fetch(`${API}/admin/spend-reset`, { method: "POST", headers });
      showToast("Counters reset");
      fetchData();
    } catch {
      showToast("Failed to reset");
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 bg-gray-200 dark:bg-slate-700 rounded animate-pulse" />
        <div className="h-48 bg-gray-200 dark:bg-slate-700 rounded animate-pulse" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-6">
        <p className="text-red-600 dark:text-red-400 text-sm font-medium">
          {error || "No data available"}
        </p>
        <p className="text-red-500 dark:text-red-500 text-xs mt-1">
          Make sure OPS_API_KEY is configured and the backend is running.
        </p>
      </div>
    );
  }

  const gaugeColor =
    data.pct_used >= 90 ? "bg-red-500" :
    data.pct_used >= 75 ? "bg-amber-500" :
    data.pct_used >= 50 ? "bg-yellow-400" :
    "bg-emerald-500";

  const statusColor =
    data.budget_breached ? "text-red-600 dark:text-red-400" :
    data.pct_used >= 75 ? "text-amber-600 dark:text-amber-400" :
    "text-emerald-600 dark:text-emerald-400";

  const paidProviders = data.providers.filter(p => p.cost_per_call > 0 || p.calls > 0);

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-gray-900 dark:bg-white text-white dark:text-gray-900 px-4 py-2 rounded-lg shadow-lg text-sm font-medium animate-pulse">
          {toast}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-gray-900 dark:text-white">
            Spend Monitor
          </h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            {data.month} &middot; Auto-refreshes every 30s
          </p>
        </div>
        <button
          onClick={resetCounters}
          className="text-xs text-gray-400 hover:text-red-500 transition"
        >
          Reset counters
        </button>
      </div>

      {/* Budget Gauge */}
      <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
        <div className="flex items-end justify-between mb-3">
          <div>
            <p className="text-3xl font-bold text-gray-900 dark:text-white">
              &euro;{data.total_spent_eur.toFixed(2)}
            </p>
            <p className={`text-sm font-medium ${statusColor}`}>
              {data.budget_breached
                ? "Budget exceeded — paid calls blocked"
                : `\u20ac${data.remaining_eur.toFixed(2)} remaining`}
            </p>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            / &euro;{data.budget_eur.toFixed(2)}
          </p>
        </div>

        {/* Progress bar */}
        <div className="h-4 bg-gray-100 dark:bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${gaugeColor}`}
            style={{ width: `${Math.min(100, data.pct_used)}%` }}
          />
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1 text-right">
          {data.pct_used.toFixed(1)}% used
        </p>

        {/* Budget editor */}
        <div className="flex items-center gap-2 mt-4 pt-4 border-t border-gray-100 dark:border-slate-700">
          <label className="text-xs text-gray-500 dark:text-gray-400 font-medium">
            Monthly cap:
          </label>
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-400">&euro;</span>
            <input
              type="number"
              value={budgetInput}
              onChange={(e) => setBudgetInput(e.target.value)}
              className="w-24 px-2 py-1 text-sm border border-gray-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-[#81D8D0] focus:border-transparent outline-none"
              min="0"
              step="10"
            />
          </div>
          <button
            onClick={updateBudget}
            disabled={saving}
            className="px-3 py-1 text-xs font-medium text-white bg-[#81D8D0] hover:bg-[#5FBFB6] rounded-lg transition disabled:opacity-50"
          >
            {saving ? "Saving..." : "Update"}
          </button>
        </div>
      </div>

      {/* Provider Breakdown */}
      <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800">
        <div className="px-6 py-4 border-b border-gray-100 dark:border-slate-700">
          <h3 className="text-sm font-bold text-gray-900 dark:text-white">
            Provider Breakdown
          </h3>
        </div>
        <div className="divide-y divide-gray-100 dark:divide-slate-700">
          {paidProviders.map((p) => {
            const providerPct = data.total_spent_eur > 0
              ? (p.spent_eur / data.total_spent_eur) * 100
              : 0;
            return (
              <div
                key={p.provider}
                className="px-6 py-3 flex items-center gap-4"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                      {p.provider}
                    </p>
                    {p.paused && (
                      <span className="px-1.5 py-0.5 text-[10px] font-bold uppercase bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 rounded">
                        Paused
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    {p.calls.toLocaleString()} calls &middot; ~&euro;{p.cost_per_call.toFixed(4)}/call
                  </p>
                </div>

                {/* Mini bar */}
                <div className="w-24 hidden sm:block">
                  <div className="h-1.5 bg-gray-100 dark:bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[#81D8D0] rounded-full"
                      style={{ width: `${Math.min(100, providerPct)}%` }}
                    />
                  </div>
                </div>

                <p className="text-sm font-mono font-medium text-gray-700 dark:text-gray-300 w-20 text-right">
                  &euro;{p.spent_eur.toFixed(2)}
                </p>

                <button
                  onClick={() => togglePause(p.provider, p.paused)}
                  className={`px-2 py-1 text-[10px] font-medium rounded-lg transition ${
                    p.paused
                      ? "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-200"
                      : "bg-gray-100 dark:bg-slate-700 text-gray-500 dark:text-gray-400 hover:bg-red-100 hover:text-red-600"
                  }`}
                >
                  {p.paused ? "Resume" : "Pause"}
                </button>
              </div>
            );
          })}
          {paidProviders.length === 0 && (
            <div className="px-6 py-8 text-center text-sm text-gray-400 dark:text-gray-500">
              No API calls recorded yet this month
            </div>
          )}
        </div>
      </div>

      {/* Recent Calls */}
      {data.recent_calls.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800">
          <div className="px-6 py-4 border-b border-gray-100 dark:border-slate-700">
            <h3 className="text-sm font-bold text-gray-900 dark:text-white">
              Recent Calls
            </h3>
          </div>
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-400 dark:text-gray-500 border-b border-gray-100 dark:border-slate-700">
                  <th className="px-6 py-2 text-left font-medium">Time</th>
                  <th className="px-2 py-2 text-left font-medium">Provider</th>
                  <th className="px-2 py-2 text-right font-medium">Cost</th>
                  <th className="px-6 py-2 text-right font-medium">Running Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-slate-700">
                {[...data.recent_calls].reverse().map((call, i) => (
                  <tr key={i} className="text-gray-600 dark:text-gray-400">
                    <td className="px-6 py-1.5 font-mono">
                      {new Date(call.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="px-2 py-1.5">{call.provider}</td>
                    <td className="px-2 py-1.5 text-right font-mono">
                      &euro;{call.cost_eur.toFixed(4)}
                    </td>
                    <td className="px-6 py-1.5 text-right font-mono">
                      &euro;{call.running_total.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Telegram Status */}
      <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
        <div className="flex items-center gap-2">
          <svg className="h-4 w-4 text-blue-500" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.161c-.18 1.897-.962 6.502-1.359 8.627-.168.9-.5 1.201-.82 1.23-.697.064-1.226-.461-1.901-.903-1.056-.692-1.653-1.123-2.678-1.799-1.185-.781-.417-1.21.258-1.911.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.479.33-.913.492-1.302.486-.429-.008-1.252-.242-1.865-.442-.751-.244-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.831-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635.099-.002.321.023.465.14.121.098.154.23.17.331.015.102.034.332.019.512z" />
          </svg>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Telegram alerts fire at <b>75%</b>, <b>90%</b>, and <b>100%</b> of budget.
            Set <code className="px-1 py-0.5 bg-gray-100 dark:bg-slate-700 rounded text-[10px]">TELEGRAM_BOT_TOKEN</code> and{" "}
            <code className="px-1 py-0.5 bg-gray-100 dark:bg-slate-700 rounded text-[10px]">TELEGRAM_CHAT_ID</code> in .env to enable.
          </p>
        </div>
      </div>
    </div>
  );
}
