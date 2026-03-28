"use client";

import { useState, useEffect } from "react";

const LS_KEY = "pipeline-rules";

interface Rule {
  id: string;
  description: string;
  enabled: boolean;
  triggeredCount: number;
}

const DEFAULT_RULES: Rule[] = [
  { id: "auto-posted", description: "Auto-advance to Posted when video URL is added", enabled: false, triggeredCount: 0 },
  { id: "auto-tracking", description: "Auto-advance to Tracking 24h after posting", enabled: false, triggeredCount: 0 },
  { id: "flag-overdue", description: "Flag overdue items (>2 days past due date)", enabled: false, triggeredCount: 0 },
  { id: "auto-assign", description: "Auto-assign to pod lead when unassigned >24h", enabled: false, triggeredCount: 0 },
];

interface LogEntry { timestamp: string; rule: string; item: string; action: string }

const MOCK_LOG: LogEntry[] = [
  { timestamp: "2026-03-28 09:12", rule: "auto-posted", item: "Pokemon Unboxing #42", action: "Advanced to Posted" },
  { timestamp: "2026-03-28 08:45", rule: "flag-overdue", item: "MTG Market Analysis", action: "Flagged as overdue" },
  { timestamp: "2026-03-27 22:30", rule: "auto-tracking", item: "Funko Haul Review", action: "Advanced to Tracking" },
  { timestamp: "2026-03-27 18:15", rule: "auto-assign", item: "Sneaker Comparison", action: "Assigned to pod lead" },
  { timestamp: "2026-03-27 14:00", rule: "auto-posted", item: "Vinyl Top 10", action: "Advanced to Posted" },
  { timestamp: "2026-03-27 11:20", rule: "flag-overdue", item: "Watch Grading Guide", action: "Flagged as overdue" },
  { timestamp: "2026-03-26 20:45", rule: "auto-tracking", item: "Warhammer Unboxing", action: "Advanced to Tracking" },
  { timestamp: "2026-03-26 16:10", rule: "auto-assign", item: "K-pop Collection Tour", action: "Assigned to pod lead" },
  { timestamp: "2026-03-26 09:30", rule: "auto-posted", item: "LEGO Deal Hunt", action: "Advanced to Posted" },
  { timestamp: "2026-03-25 23:00", rule: "flag-overdue", item: "Yu-Gi-Oh Price Check", action: "Flagged as overdue" },
];

function load(): Rule[] {
  if (typeof window === "undefined") return DEFAULT_RULES;
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : DEFAULT_RULES;
  } catch { return DEFAULT_RULES; }
}

function save(r: Rule[]) { localStorage.setItem(LS_KEY, JSON.stringify(r)); }

export function PipelineAutomation() {
  const [rules, setRules] = useState<Rule[]>(DEFAULT_RULES);

  useEffect(() => { setRules(load()); }, []);

  const toggle = (id: string) => {
    setRules((prev) => {
      const next = prev.map((r) => r.id === id ? { ...r, enabled: !r.enabled, triggeredCount: r.triggeredCount + (r.enabled ? 0 : Math.floor(Math.random() * 5)) } : r);
      save(next);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-white dark:bg-slate-800 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">Pipeline Automation Rules</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-5">Configure automatic actions for your content pipeline.</p>

        <div className="space-y-3">
          {rules.map((rule) => (
            <div key={rule.id} className="flex items-center justify-between rounded-xl border border-gray-200 dark:border-slate-700 p-4">
              <div className="flex-1 mr-4">
                <p className="text-sm font-medium text-gray-900 dark:text-white">{rule.description}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Triggered {rule.triggeredCount} time(s)</p>
              </div>
              <button
                onClick={() => toggle(rule.id)}
                className={`relative w-11 h-6 rounded-full transition flex-shrink-0 ${rule.enabled ? "bg-[#81D8D0]" : "bg-gray-300 dark:bg-slate-600"}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${rule.enabled ? "translate-x-5" : ""}`} />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-2xl bg-white dark:bg-slate-800 shadow-sm p-6">
        <h3 className="text-md font-semibold text-gray-900 dark:text-white mb-4">Automation Log</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-slate-700">
                <th className="pb-2 font-medium">Time</th>
                <th className="pb-2 font-medium">Item</th>
                <th className="pb-2 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {MOCK_LOG.map((entry, i) => (
                <tr key={i} className="border-b border-gray-100 dark:border-slate-700/50 last:border-0">
                  <td className="py-2 text-gray-500 dark:text-gray-400 whitespace-nowrap">{entry.timestamp}</td>
                  <td className="py-2 text-gray-900 dark:text-white">{entry.item}</td>
                  <td className="py-2 text-gray-600 dark:text-gray-300">{entry.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
