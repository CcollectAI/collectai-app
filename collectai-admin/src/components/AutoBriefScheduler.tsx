"use client";

import { useState, useEffect } from "react";
import { APP_CONFIG } from "../../admin.config";
import { getSupabase } from "@/lib/supabase";

type BriefState = Record<string, { enabled: boolean; lastGenerated: string | null }>;

const LS_KEY = "auto-briefs";

function loadFromLocalStorage(): BriefState {
  if (typeof window === "undefined") return {};
  try { return JSON.parse(localStorage.getItem(LS_KEY) || "{}"); } catch { return {}; }
}

function saveToLocalStorage(s: BriefState) {
  localStorage.setItem(LS_KEY, JSON.stringify(s));
}

async function loadFromSupabase(): Promise<BriefState | null> {
  const sb = getSupabase();
  if (!sb) return null;
  try {
    const { data, error } = await sb
      .from("admin_content_config")
      .select("*")
      .eq("config_type", "brief");
    if (error || !data) return null;
    const state: BriefState = {};
    for (const row of data) {
      const podId = (row.id as string).replace(/^brief:/, "");
      state[podId] = row.data as { enabled: boolean; lastGenerated: string | null };
    }
    return state;
  } catch {
    return null;
  }
}

async function saveToSupabase(state: BriefState): Promise<boolean> {
  const sb = getSupabase();
  if (!sb) return false;
  try {
    const rows = Object.entries(state).map(([podId, data]) => ({
      id: `brief:${podId}`,
      config_type: "brief",
      data,
      updated_at: new Date().toISOString(),
    }));
    if (rows.length === 0) return true;
    const { error } = await sb
      .from("admin_content_config")
      .upsert(rows, { onConflict: "id" });
    return !error;
  } catch {
    return false;
  }
}

export function AutoBriefScheduler() {
  const [state, setState] = useState<BriefState>({});
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const sbState = await loadFromSupabase();
      if (!cancelled) {
        if (sbState !== null && Object.keys(sbState).length > 0) {
          setState(sbState);
        } else {
          setState(loadFromLocalStorage());
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const persist = async (next: BriefState) => {
    const ok = await saveToSupabase(next);
    if (!ok) saveToLocalStorage(next);
  };

  const toggle = (id: string) => {
    setState((prev) => {
      const cur = prev[id] || { enabled: false, lastGenerated: null };
      const next = { ...prev, [id]: { ...cur, enabled: !cur.enabled } };
      persist(next);
      return next;
    });
  };

  const generate = (id: string) => {
    setState((prev) => {
      const next = { ...prev, [id]: { ...prev[id], enabled: prev[id]?.enabled ?? true, lastGenerated: new Date().toISOString() } };
      persist(next);
      return next;
    });
  };

  const generateAll = async () => {
    setGenerating(true);
    const active = APP_CONFIG.pods.filter((p) => state[p.id]?.enabled);
    const next = { ...state };
    const now = new Date().toISOString();
    active.forEach((p) => { next[p.id] = { ...next[p.id], lastGenerated: now }; });
    await persist(next);
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
