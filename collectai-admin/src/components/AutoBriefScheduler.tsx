"use client";

import { useState, useEffect } from "react";
import { APP_CONFIG } from "../../admin.config";

type BriefState = Record<string, { enabled: boolean; lastGenerated: string | null }>;

const LS_KEY = "auto-briefs";

function load(): BriefState {
  if (typeof window === "undefined") return {};
  try { return JSON.parse(localStorage.getItem(LS_KEY) || "{}"); } catch { return {}; }
}

function save(s: BriefState) { localStorage.setItem(LS_KEY, JSON.stringify(s)); }

export function AutoBriefScheduler() {
  const [state, setState] = useState<BriefState>({});
  const [generating, setGenerating] = useState(false);

  useEffect(() => { setState(load()); }, []);

  const toggle = (id: string) => {
    setState((prev) => {
      const cur = prev[id] || { enabled: false, lastGenerated: null };
      const next = { ...prev, [id]: { ...cur, enabled: !cur.enabled } };
      save(next);
      return next;
    });
  };

  const generate = (id: string) => {
    setState((prev) => {
      const next = { ...prev, [id]: { ...prev[id], enabled: prev[id]?.enabled ?? true, lastGenerated: new Date().toISOString() } };
      save(next);
      return next;
    });
  };

  const generateAll = async () => {
    setGenerating(true);
    const active = APP_CONFIG.pods.filter((p) => state[p.id]?.enabled);
    const next = { ...state };
    const now = new Date().toISOString();
    active.forEach((p) => { next[p.id] = { ...next[p.id], lastGenerated: now }; });
    save(next);
    setState(next);
    setTimeout(() => setGenerating(false), 800);
  };

  const activeCount = APP_CONFIG.pods.filter((p) => state[p.id]?.enabled).length;

  return (
    <div className="rounded-2xl bg-white dark:bg-slate-800 shadow-sm p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Auto Brief Scheduler</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">{activeCount} pod(s) active</p>
        </div>
        <button
          onClick={generateAll}
          disabled={generating || activeCount === 0}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-[#81D8D0] hover:bg-[#5FBFB6] text-white disabled:opacity-50 transition"
        >
          {generating ? "Generating..." : "Generate All Now"}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {APP_CONFIG.pods.map((pod) => {
          const s = state[pod.id] || { enabled: false, lastGenerated: null };
          return (
            <div key={pod.id} className="rounded-xl border border-gray-200 dark:border-slate-700 p-4 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full" style={{ backgroundColor: pod.color }} />
                  <span className="font-medium text-gray-900 dark:text-white text-sm">{pod.name}</span>
                </div>
                <button
                  onClick={() => toggle(pod.id)}
                  className={`relative w-10 h-5 rounded-full transition ${s.enabled ? "bg-[#81D8D0]" : "bg-gray-300 dark:bg-slate-600"}`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${s.enabled ? "translate-x-5" : ""}`} />
                </button>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {s.lastGenerated ? `Last: ${new Date(s.lastGenerated).toLocaleDateString()}` : "Never generated"}
                </span>
                <button
                  onClick={() => generate(pod.id)}
                  className="text-xs px-3 py-1 rounded-md bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-slate-600 transition"
                >
                  Generate
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
