"use client";

import { useState, useEffect } from "react";
import { getSupabase } from "@/lib/supabase";

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
  // Video Generator automation rules
  { id: "video-hit-replicate", description: "Auto-replicate video to all pods when classified as HIT (>50K views, >40% retention)", enabled: false, triggeredCount: 3 },
  { id: "video-gap-fill", description: "Auto-generate template videos when pod falls below weekly target by Thursday", enabled: false, triggeredCount: 7 },
  { id: "video-new-release", description: "Auto-generate Market Alert video when demand signals detect vault, discontinuation, or new drop", enabled: false, triggeredCount: 12 },
  { id: "video-hook-swap", description: "Retire underperforming hooks (3+ consecutive fails) and A/B test next-best alternative", enabled: false, triggeredCount: 2 },
];

interface LogEntry { timestamp: string; rule: string; item: string; action: string }

const MOCK_LOG: LogEntry[] = [
  { timestamp: "2026-03-29 10:00", rule: "video-hit-replicate", item: "[Video] Pokemon Pull Reveal → HIT", action: "Auto-generated 5 hook variants + replicated to MTG, Funko pods" },
  { timestamp: "2026-03-29 09:30", rule: "video-new-release", item: "[Video] Yu-Gi-Oh QCSR discontinuation", action: "Auto-generated MarketAlert video for Yu-Gi-Oh pod" },
  { timestamp: "2026-03-28 09:12", rule: "auto-posted", item: "Pokemon Unboxing #42", action: "Advanced to Posted" },
  { timestamp: "2026-03-28 08:45", rule: "flag-overdue", item: "MTG Market Analysis", action: "Flagged as overdue" },
  { timestamp: "2026-03-27 22:30", rule: "auto-tracking", item: "Funko Haul Review", action: "Advanced to Tracking" },
  { timestamp: "2026-03-27 18:15", rule: "video-gap-fill", item: "[Video] Watches Pod below target", action: "Auto-generated 2 template videos (WhatsItWorth, CollectionFlex)" },
  { timestamp: "2026-03-27 14:00", rule: "auto-posted", item: "Vinyl Top 10", action: "Advanced to Posted" },
  { timestamp: "2026-03-27 11:20", rule: "video-hook-swap", item: "[Video] Hook dyk-3 retired for Sneakers", action: "Swapped to hook dyk-5 (higher retention estimate)" },
  { timestamp: "2026-03-26 20:45", rule: "auto-tracking", item: "Warhammer Unboxing", action: "Advanced to Tracking" },
  { timestamp: "2026-03-26 16:10", rule: "auto-assign", item: "K-pop Collection Tour", action: "Assigned to pod lead" },
  { timestamp: "2026-03-26 09:30", rule: "auto-posted", item: "LEGO Deal Hunt", action: "Advanced to Posted" },
  { timestamp: "2026-03-25 23:00", rule: "flag-overdue", item: "Yu-Gi-Oh What's It Worth", action: "Flagged as overdue" },
];

function loadFromLocalStorage(): Rule[] {
  if (typeof window === "undefined") return DEFAULT_RULES;
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : DEFAULT_RULES;
  } catch { return DEFAULT_RULES; }
}

function saveToLocalStorage(r: Rule[]) {
  localStorage.setItem(LS_KEY, JSON.stringify(r));
}

async function loadRulesFromSupabase(): Promise<Rule[] | null> {
  const sb = getSupabase();
  if (!sb) return null;
  try {
    const { data, error } = await sb
      .from("admin_content_config")
      .select("*")
      .eq("config_type", "rule");
    if (error || !data || data.length === 0) return null;
    return data.map((row) => row.data as Rule);
  } catch {
    return null;
  }
}

async function saveRuleToSupabase(rule: Rule): Promise<boolean> {
  const sb = getSupabase();
  if (!sb) return false;
  try {
    const { error } = await sb
      .from("admin_content_config")
      .upsert({
        id: `rule:${rule.id}`,
        config_type: "rule",
        data: rule,
        updated_at: new Date().toISOString(),
      }, { onConflict: "id" });
    return !error;
  } catch {
    return false;
  }
}

async function loadLogFromSupabase(): Promise<LogEntry[] | null> {
  const sb = getSupabase();
  if (!sb) return null;
  try {
    const { data, error } = await sb
      .from("admin_content_config")
      .select("*")
      .eq("config_type", "rule_log")
      .order("updated_at", { ascending: false })
      .limit(20);
    if (error || !data || data.length === 0) return null;
    return data.map((row) => row.data as LogEntry);
  } catch {
    return null;
  }
}

export function PipelineAutomation() {
  const [rules, setRules] = useState<Rule[]>(DEFAULT_RULES);
  const [log, setLog] = useState<LogEntry[]>(MOCK_LOG);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [sbRules, sbLog] = await Promise.all([
        loadRulesFromSupabase(),
        loadLogFromSupabase(),
      ]);
      if (!cancelled) {
        if (sbRules !== null) {
          setRules(sbRules);
        } else {
          setRules(loadFromLocalStorage());
        }
        if (sbLog !== null) {
          setLog(sbLog);
        }
        // If sbLog is null, keep MOCK_LOG as default
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const toggle = (id: string) => {
    setRules((prev) => {
      const next = prev.map((r) => r.id === id ? { ...r, enabled: !r.enabled, triggeredCount: r.triggeredCount + (r.enabled ? 0 : Math.floor(Math.random() * 5)) } : r);
      const updated = next.find((r) => r.id === id);
      if (updated) {
        saveRuleToSupabase(updated).then((ok) => {
          if (!ok) saveToLocalStorage(next);
        });
      }
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
              {log.map((entry, i) => (
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
