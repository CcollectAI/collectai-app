"use client";

import { useState, useEffect } from "react";

const LS_KEY = "digest-schedules";
const DIGEST_TYPES = ["Weekly Pod Report", "Commission Summary", "KPI Snapshot", "UGC Performance"] as const;
const FREQUENCIES = ["Weekly", "Bi-weekly", "Monthly"] as const;
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] as const;
const FORMATS = ["Markdown", "CSV", "WhatsApp"] as const;

interface Schedule {
  id: string;
  type: string;
  frequency: string;
  day: string;
  format: string;
  recipients: string;
  createdAt: string;
}

function load(): Schedule[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch { return []; }
}

function save(s: Schedule[]) { localStorage.setItem(LS_KEY, JSON.stringify(s)); }

const selectClass = "w-full rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-700 text-gray-900 dark:text-white text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#81D8D0]";

export function DigestScheduler() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [type, setType] = useState<string>(DIGEST_TYPES[0]);
  const [frequency, setFrequency] = useState<string>(FREQUENCIES[0]);
  const [day, setDay] = useState<string>(DAYS[0]);
  const [format, setFormat] = useState<string>(FORMATS[0]);
  const [recipients, setRecipients] = useState("");

  useEffect(() => { setSchedules(load()); }, []);

  const addSchedule = () => {
    if (!recipients.trim()) return;
    const s: Schedule = { id: Date.now().toString(), type, frequency, day, format, recipients: recipients.trim(), createdAt: new Date().toISOString() };
    const next = [s, ...schedules];
    save(next);
    setSchedules(next);
    setRecipients("");
  };

  const remove = (id: string) => {
    const next = schedules.filter((s) => s.id !== id);
    save(next);
    setSchedules(next);
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-white dark:bg-slate-800 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">Digest Scheduler</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-5">Schedule automated digest exports for your team.</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Digest Type</label>
            <select value={type} onChange={(e) => setType(e.target.value)} className={selectClass}>
              {DIGEST_TYPES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Frequency</label>
            <select value={frequency} onChange={(e) => setFrequency(e.target.value)} className={selectClass}>
              {FREQUENCIES.map((f) => <option key={f}>{f}</option>)}
            </select>
          </div>
          {frequency === "Weekly" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Day of Week</label>
              <select value={day} onChange={(e) => setDay(e.target.value)} className={selectClass}>
                {DAYS.map((d) => <option key={d}>{d}</option>)}
              </select>
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Export Format</label>
            <select value={format} onChange={(e) => setFormat(e.target.value)} className={selectClass}>
              {FORMATS.map((f) => <option key={f}>{f}</option>)}
            </select>
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Recipients (comma-separated)</label>
          <input
            type="text"
            value={recipients}
            onChange={(e) => setRecipients(e.target.value)}
            placeholder="alice@team.com, bob@team.com"
            className="w-full rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-700 text-gray-900 dark:text-white text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#81D8D0]"
          />
        </div>

        <button onClick={addSchedule} disabled={!recipients.trim()} className="px-5 py-2 text-sm font-medium rounded-lg bg-[#81D8D0] hover:bg-[#5FBFB6] text-white disabled:opacity-50 transition">
          Schedule
        </button>
      </div>

      {schedules.length > 0 && (
        <div className="rounded-2xl bg-white dark:bg-slate-800 shadow-sm p-6">
          <h3 className="text-md font-semibold text-gray-900 dark:text-white mb-4">Active Schedules</h3>
          <div className="space-y-3">
            {schedules.map((s) => (
              <div key={s.id} className="flex items-center justify-between rounded-xl border border-gray-200 dark:border-slate-700 p-4">
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">{s.type} — {s.frequency}{s.frequency === "Weekly" ? ` (${s.day})` : ""}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{s.format} to {s.recipients}</p>
                </div>
                <button onClick={() => remove(s.id)} className="text-xs text-red-500 hover:text-red-700 dark:hover:text-red-400 transition">Remove</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
