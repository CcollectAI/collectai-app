"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell,
} from "recharts";
import { MetricCard } from "@/components/ui/MetricCard";
import { getSupabase } from "@/lib/supabase";
import { APP_CONFIG } from "../../admin.config";

/* ───────────────────────── Types ───────────────────────── */

interface Issue {
  id: string;
  title: string;
  description: string;
  priority: "critical" | "high" | "medium" | "low";
  status: "open" | "in_progress" | "resolved" | "closed";
  reporter: string;
  assignee: string;
  created_at: string;
  updated_at: string;
  source: "internal" | "user_report" | "automated";
}

interface Feedback {
  id: string;
  user_email: string;
  subject: string;
  message: string;
  category: "bug" | "feature_request" | "improvement" | "question" | "praise";
  status: "new" | "reviewed" | "actioned" | "archived";
  created_at: string;
  notes: string;
}

interface Deploy {
  version: string;
  date: string;
  status: string;
  duration: string;
  changes: string;
}

interface ErrorRatePoint {
  day: string;
  rate: number;
}

/* ───────────────────────── Constants ───────────────────── */

const TIFFANY = "#81D8D0";
const LS_ISSUES = "dev-issues";
const LS_FEEDBACK = "dev-feedback";

const API = APP_CONFIG.api.baseUrl;
const API_HEADERS: Record<string, string> = {
  "X-Ops-Key": APP_CONFIG.api.opsKey,
  "Content-Type": "application/json",
};

const PRIORITY_COLOR: Record<Issue["priority"], string> = {
  critical: "bg-red-500", high: "bg-amber-500", medium: "bg-blue-500", low: "bg-gray-400",
};
const STATUS_BADGE: Record<Issue["status"], string> = {
  open: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  in_progress: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  resolved: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  closed: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400",
};
const FB_CAT_CHIP: Record<Feedback["category"], string> = {
  bug: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  feature_request: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  improvement: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  question: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  praise: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
};
const FB_STATUS_BADGE: Record<Feedback["status"], string> = {
  new: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  reviewed: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  actioned: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  archived: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400",
};

const uid = () => Math.random().toString(36).slice(2, 10);
const now = () => new Date().toISOString();
const fmtDate = (d: string) => new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric" });

/* ───────────────────────── Seed Data ────────────────────── */

const SEED_ISSUES: Issue[] = [
  { id: uid(), title: "Push notification delivery fails on iOS 17.4", description: "APNs returns InvalidProviderToken for ~12% of iOS 17.4 devices after token refresh.", priority: "critical", status: "open", reporter: "ops-monitor", assignee: "Backend", created_at: "2026-03-26T09:15:00Z", updated_at: "2026-03-26T09:15:00Z", source: "internal" },
  { id: uid(), title: "Dark mode contrast issue on collection grid", description: "Card text on collection grid is hard to read in dark mode when item has no image.", priority: "medium", status: "in_progress", reporter: "sarah.k@outlook.com", assignee: "Frontend", created_at: "2026-03-25T14:30:00Z", updated_at: "2026-03-26T10:00:00Z", source: "user_report" },
  { id: uid(), title: "Price prediction timeout for watches > $10K", description: "Ridge regression inference exceeds 5s timeout for luxury watches with sparse comps.", priority: "high", status: "open", reporter: "ml-pipeline", assignee: "ML Team", created_at: "2026-03-24T08:00:00Z", updated_at: "2026-03-24T08:00:00Z", source: "automated" },
  { id: uid(), title: "Duplicate barcode scan results", description: "QuickScan returns 2-3 duplicate entries when scanning barcodes under low light.", priority: "high", status: "resolved", reporter: "pokefan99@gmail.com", assignee: "Frontend", created_at: "2026-03-22T11:45:00Z", updated_at: "2026-03-25T16:20:00Z", source: "user_report" },
  { id: uid(), title: "Marketplace adapter StockX rate limit", description: "StockX adapter hitting 429s after ~200 requests/min. Need to implement backoff.", priority: "medium", status: "open", reporter: "adapter-health", assignee: "Backend", created_at: "2026-03-21T07:30:00Z", updated_at: "2026-03-21T07:30:00Z", source: "automated" },
  { id: uid(), title: "Export CSV missing currency symbol", description: "CSV export omits currency prefix for non-USD currencies.", priority: "low", status: "closed", reporter: "numis.collector@yahoo.com", assignee: "Frontend", created_at: "2026-03-18T10:00:00Z", updated_at: "2026-03-20T09:00:00Z", source: "user_report" },
];

const SEED_FEEDBACK: Feedback[] = [
  { id: uid(), user_email: "collector42@gmail.com", subject: "Would love a wishlist sharing feature", message: "It would be awesome if I could share my wishlist with friends so they know what to get me for my birthday. Maybe a public link or QR code?", category: "feature_request", status: "new", created_at: "2026-03-27T10:00:00Z", notes: "" },
  { id: uid(), user_email: "sarah.k@outlook.com", subject: "App crashes when adding 50+ photos to one item", message: "I tried to add 60 photos of my vintage watch from different angles and the app crashed. iPhone 15 Pro, iOS 17.4. Happened 3 times.", category: "bug", status: "reviewed", created_at: "2026-03-26T15:30:00Z", notes: "Likely memory pressure from full-res loading. Needs image downsample before gallery insert." },
  { id: uid(), user_email: "pokefan99@gmail.com", subject: "Love the QuickScan! Works great for Pokemon cards", message: "Just wanted to say the QuickScan feature is incredible. I scanned my entire binder of 200 cards in under 30 minutes. Keep up the great work!", category: "praise", status: "archived", created_at: "2026-03-25T08:00:00Z", notes: "" },
  { id: uid(), user_email: "numis.collector@yahoo.com", subject: "Can you add support for coin grading (NGC/PCGS)?", message: "I collect graded coins and would love to input NGC/PCGS grades and have the app factor that into valuations. Slab photos would be great too.", category: "feature_request", status: "new", created_at: "2026-03-24T12:45:00Z", notes: "" },
];

const FALLBACK_ERROR_RATE_DATA: ErrorRatePoint[] = Array.from({ length: 14 }, (_, i) => ({
  day: `Mar ${15 + i}`,
  rate: +(0.05 + Math.random() * 0.2).toFixed(3),
}));

const FALLBACK_DEPLOYS: Deploy[] = [
  { version: "v2.4.1", date: "Today", status: "Success", duration: "3m 42s", changes: "Fix push notification iOS 17.4" },
  { version: "v2.4.0", date: "Yesterday", status: "Success", duration: "4m 15s", changes: "Pro-grade admin dashboard" },
  { version: "v2.3.9", date: "3 days ago", status: "Success", duration: "3m 58s", changes: "Notification overhaul" },
  { version: "v2.3.8", date: "5 days ago", status: "Failed", duration: "1m 22s", changes: "ML model retrain pipeline" },
  { version: "v2.3.7", date: "7 days ago", status: "Success", duration: "4m 01s", changes: "Category expansion round 3" },
];

/* ───────────────────────── Helpers ───────────────────────── */

const EMPTY_ISSUE: Omit<Issue, "id" | "created_at" | "updated_at"> = {
  title: "", description: "", priority: "medium", status: "open", reporter: "", assignee: "", source: "internal",
};
const EMPTY_FB: Omit<Feedback, "id" | "created_at" | "notes"> = {
  user_email: "", subject: "", message: "", category: "bug", status: "new",
};

const inputCls = "rounded-lg border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2 text-sm text-gray-900 dark:text-white w-full";
const cardCls = "bg-white dark:bg-slate-800 rounded-2xl shadow-sm p-5 transition-colors";
const headCls = "text-lg font-semibold text-gray-900 dark:text-white";

/* ─────────────── Supabase-backed persistence hook ─────────────── */

/**
 * useSupabasePersisted — tries Supabase `admin_dev_hub` table first,
 * falls back to localStorage. Every write goes to both (Supabase primary,
 * localStorage backup). Seeds are only used when both stores are empty.
 */
function useSupabasePersisted<T extends { id: string }>(
  itemType: "issue" | "feedback",
  lsKey: string,
  seed: T[],
): [T[], React.Dispatch<React.SetStateAction<T[]>>] {
  const [data, setDataRaw] = useState<T[]>(seed);
  const initialized = useRef(false);
  const supabaseOk = useRef(false);

  // ── Initial load ──
  useEffect(() => {
    let cancelled = false;

    async function load() {
      const sb = getSupabase();

      // 1) Try Supabase
      if (sb) {
        try {
          const { data: rows, error } = await sb
            .from("admin_dev_hub")
            .select("id, data")
            .eq("item_type", itemType)
            .order("created_at", { ascending: false });

          if (!error && rows && rows.length > 0) {
            if (!cancelled) {
              const items = rows.map((r: { id: string; data: T }) => r.data);
              setDataRaw(items);
              supabaseOk.current = true;
              initialized.current = true;
              // Sync to localStorage as backup
              try { localStorage.setItem(lsKey, JSON.stringify(items)); } catch { /* noop */ }
              return;
            }
          }

          // Supabase is reachable but table is empty — we'll check localStorage next
          if (!error) {
            supabaseOk.current = true;
          }
        } catch {
          // Supabase unavailable, fall through to localStorage
        }
      }

      // 2) Try localStorage
      if (!cancelled) {
        try {
          const raw = localStorage.getItem(lsKey);
          if (raw) {
            const parsed = JSON.parse(raw) as T[];
            if (parsed.length > 0) {
              setDataRaw(parsed);
              initialized.current = true;
              // Back-fill Supabase if it was reachable but empty
              if (supabaseOk.current && sb) {
                _syncAllToSupabase(sb, itemType, parsed).catch(() => {});
              }
              return;
            }
          }
        } catch { /* use seed */ }

        // 3) Both empty — use seed and persist
        setDataRaw(seed);
        initialized.current = true;
        try { localStorage.setItem(lsKey, JSON.stringify(seed)); } catch { /* noop */ }
        if (supabaseOk.current && sb) {
          _syncAllToSupabase(sb, itemType, seed).catch(() => {});
        }
      }
    }

    load();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemType, lsKey]);

  // ── Wrapped setter: writes to both stores ──
  const setData: React.Dispatch<React.SetStateAction<T[]>> = useCallback(
    (action) => {
      setDataRaw((prev) => {
        const next = typeof action === "function" ? (action as (p: T[]) => T[])(prev) : action;

        // localStorage backup (always)
        try { localStorage.setItem(lsKey, JSON.stringify(next)); } catch { /* noop */ }

        // Supabase primary (async, fire-and-forget)
        const sb = getSupabase();
        if (sb) {
          _diffAndSync(sb, itemType, prev, next).catch(() => {});
        }

        return next;
      });
    },
    [lsKey, itemType],
  );

  return [data, setData];
}

/* ── Supabase sync helpers ── */

async function _syncAllToSupabase<T extends { id: string }>(
  sb: NonNullable<ReturnType<typeof getSupabase>>,
  itemType: string,
  items: T[],
) {
  const rows = items.map((item) => ({
    id: `${itemType}_${item.id}`,
    item_type: itemType,
    data: item,
    created_at: (item as Record<string, unknown>).created_at ?? new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }));
  if (rows.length > 0) {
    await sb.from("admin_dev_hub").upsert(rows, { onConflict: "id" });
  }
}

async function _diffAndSync<T extends { id: string }>(
  sb: NonNullable<ReturnType<typeof getSupabase>>,
  itemType: string,
  prev: T[],
  next: T[],
) {
  const prevIds = new Set(prev.map((i) => i.id));
  const nextIds = new Set(next.map((i) => i.id));

  // Deletions
  const deleted = prev.filter((i) => !nextIds.has(i.id));
  if (deleted.length > 0) {
    const ids = deleted.map((i) => `${itemType}_${i.id}`);
    await sb.from("admin_dev_hub").delete().in("id", ids);
  }

  // Upserts (new + updated — just upsert everything in `next` for simplicity)
  const upserts = next.map((item) => ({
    id: `${itemType}_${item.id}`,
    item_type: itemType,
    data: item,
    created_at: (item as Record<string, unknown>).created_at ?? new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }));
  if (upserts.length > 0) {
    await sb.from("admin_dev_hub").upsert(upserts, { onConflict: "id" });
  }
}

/* ═══════════════════════ COMPONENT ══════════════════════ */

export function DeveloperHub() {
  const [issues, setIssues] = useSupabasePersisted<Issue>("issue", LS_ISSUES, SEED_ISSUES);
  const [feedback, setFeedback] = useSupabasePersisted<Feedback>("feedback", LS_FEEDBACK, SEED_FEEDBACK);

  /* ---- Backend-fetched data with fallback ---- */
  const [errorRateData, setErrorRateData] = useState<ErrorRatePoint[]>(FALLBACK_ERROR_RATE_DATA);
  const [deploys, setDeploys] = useState<Deploy[]>(FALLBACK_DEPLOYS);

  useEffect(() => {
    async function fetchErrorRate() {
      try {
        const res = await fetch(`${API}/admin/error-rate`, { headers: API_HEADERS });
        if (res.ok) {
          const json = await res.json();
          if (Array.isArray(json) && json.length > 0) {
            setErrorRateData(json);
          }
        }
      } catch {
        // Fallback already set
      }
    }

    async function fetchDeploys() {
      try {
        const res = await fetch(`${API}/admin/deploy-history`, { headers: API_HEADERS });
        if (res.ok) {
          const json = await res.json();
          if (Array.isArray(json) && json.length > 0) {
            setDeploys(json);
          }
        }
      } catch {
        // Fallback already set
      }
    }

    fetchErrorRate();
    fetchDeploys();
  }, []);

  /* ---- Issue state ---- */
  const [showIssueForm, setShowIssueForm] = useState(false);
  const [issueDraft, setIssueDraft] = useState({ ...EMPTY_ISSUE });
  const [editId, setEditId] = useState<string | null>(null);
  const [issueFilter, setIssueFilter] = useState({ status: "", priority: "", q: "" });
  const [issueSort, setIssueSort] = useState<"priority" | "date" | "status">("priority");

  /* ---- Feedback state ---- */
  const [showFbForm, setShowFbForm] = useState(false);
  const [fbDraft, setFbDraft] = useState({ ...EMPTY_FB });
  const [expandedFb, setExpandedFb] = useState<string | null>(null);
  const [fbFilter, setFbFilter] = useState({ category: "", status: "" });

  /* ---- Issue CRUD ---- */
  const saveIssue = useCallback(() => {
    if (!issueDraft.title.trim()) return;
    if (editId) {
      setIssues(prev => prev.map(i => i.id === editId ? { ...i, ...issueDraft, updated_at: now() } : i));
      setEditId(null);
    } else {
      setIssues(prev => [{ ...issueDraft, id: uid(), created_at: now(), updated_at: now() }, ...prev]);
    }
    setIssueDraft({ ...EMPTY_ISSUE });
    setShowIssueForm(false);
  }, [issueDraft, editId, setIssues]);

  const deleteIssue = (id: string) => setIssues(prev => prev.filter(i => i.id !== id));
  const resolveIssue = (id: string) => setIssues(prev => prev.map(i => i.id === id ? { ...i, status: "resolved" as const, updated_at: now() } : i));

  const startEdit = (issue: Issue) => {
    setEditId(issue.id);
    setIssueDraft({ title: issue.title, description: issue.description, priority: issue.priority, status: issue.status, reporter: issue.reporter, assignee: issue.assignee, source: issue.source });
    setShowIssueForm(true);
  };

  /* ---- Feedback CRUD ---- */
  const saveFeedback = useCallback(() => {
    if (!fbDraft.subject.trim()) return;
    setFeedback(prev => [{ ...fbDraft, id: uid(), created_at: now(), notes: "" }, ...prev]);
    setFbDraft({ ...EMPTY_FB });
    setShowFbForm(false);
  }, [fbDraft, setFeedback]);

  const updateFbStatus = (id: string, status: Feedback["status"]) =>
    setFeedback(prev => prev.map(f => f.id === id ? { ...f, status } : f));

  const updateFbNotes = (id: string, notes: string) =>
    setFeedback(prev => prev.map(f => f.id === id ? { ...f, notes } : f));

  const convertToIssue = (fb: Feedback) => {
    const newIssue: Issue = {
      id: uid(), title: fb.subject, description: fb.message,
      priority: fb.category === "bug" ? "high" : "medium",
      status: "open", reporter: fb.user_email, assignee: "",
      created_at: now(), updated_at: now(),
      source: "user_report",
    };
    setIssues(prev => [newIssue, ...prev]);
    updateFbStatus(fb.id, "actioned");
  };

  /* ---- Filtered / sorted issues ---- */
  const PRIO_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
  const STATUS_ORDER: Record<string, number> = { open: 0, in_progress: 1, resolved: 2, closed: 3 };

  const filteredIssues = issues
    .filter(i => (!issueFilter.status || i.status === issueFilter.status)
      && (!issueFilter.priority || i.priority === issueFilter.priority)
      && (!issueFilter.q || i.title.toLowerCase().includes(issueFilter.q.toLowerCase())))
    .sort((a, b) => {
      if (issueSort === "priority") return PRIO_ORDER[a.priority] - PRIO_ORDER[b.priority];
      if (issueSort === "date") return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      return STATUS_ORDER[a.status] - STATUS_ORDER[b.status];
    });

  const filteredFb = feedback
    .filter(f => (!fbFilter.category || f.category === fbFilter.category) && (!fbFilter.status || f.status === fbFilter.status));

  /* ═══════════════════════ RENDER ═══════════════════════ */

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Developer Hub</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">Bugs, feedback &amp; engineering metrics</p>
      </div>

      {/* S1: KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Backend Tests" value={3194} trend={3.8} sparklineData={[2800,2900,2950,3000,3078,3194]} subtitle="+116 this round" />
        <MetricCard label="Frontend Tests" value={476} trend={9.7} sparklineData={[380,400,420,434,458,476]} subtitle="+42 this round" />
        <MetricCard label="TS Errors" value={0} trend={0} subtitle="Clean build" />
        <MetricCard label="API Endpoints" value={95} suffix="+" subtitle="43 routers" />
        <MetricCard label="Avg API Latency" value={142} suffix="ms" trend={-5.3} subtitle="-8ms vs last week" />
        <MetricCard label="Error Rate (24h)" value={0.12} suffix="%" trend={-20} subtitle="-0.03% vs yesterday" />
        <MetricCard label="Build Time" value={4.6} suffix="s" subtitle="EAS Build" />
        <MetricCard label="Uptime (30d)" value={99.97} suffix="%" subtitle="99.97% SLA" />
      </div>

      {/* S2: Error Rate Trend */}
      <div className={cardCls}>
        <h2 className={headCls}>Error Rate Trend (14d)</h2>
        <div className="h-48 mt-3">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={errorRateData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} stroke="#94a3b8" />
              <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" unit="%" />
              <Tooltip formatter={(v) => `${Number(v).toFixed(3)}%`} />
              <Area type="monotone" dataKey="rate" stroke={TIFFANY} fill={TIFFANY} fillOpacity={0.25} strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* S3: Bug Tracker */}
      <div className={cardCls}>
        <div className="flex items-center justify-between mb-4">
          <h2 className={headCls}>Issues / Bug Tracker</h2>
          <button onClick={() => { setShowIssueForm(!showIssueForm); setEditId(null); setIssueDraft({ ...EMPTY_ISSUE }); }}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white" style={{ backgroundColor: TIFFANY }}>
            {showIssueForm ? "Cancel" : "New Issue"}
          </button>
        </div>

        {/* Inline form */}
        {showIssueForm && (
          <div className="bg-gray-50 dark:bg-slate-700 border border-gray-200 dark:border-slate-600 rounded-lg p-4 mb-4 grid grid-cols-2 gap-3">
            <input className={inputCls} placeholder="Title" value={issueDraft.title} onChange={e => setIssueDraft(d => ({ ...d, title: e.target.value }))} />
            <select className={inputCls} value={issueDraft.priority} onChange={e => setIssueDraft(d => ({ ...d, priority: e.target.value as Issue["priority"] }))}>
              <option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
            </select>
            <textarea className={`${inputCls} col-span-2`} rows={2} placeholder="Description" value={issueDraft.description} onChange={e => setIssueDraft(d => ({ ...d, description: e.target.value }))} />
            <select className={inputCls} value={issueDraft.status} onChange={e => setIssueDraft(d => ({ ...d, status: e.target.value as Issue["status"] }))}>
              <option value="open">Open</option><option value="in_progress">In Progress</option><option value="resolved">Resolved</option><option value="closed">Closed</option>
            </select>
            <select className={inputCls} value={issueDraft.source} onChange={e => setIssueDraft(d => ({ ...d, source: e.target.value as Issue["source"] }))}>
              <option value="internal">Internal</option><option value="user_report">User Report</option><option value="automated">Automated</option>
            </select>
            <input className={inputCls} placeholder="Reporter" value={issueDraft.reporter} onChange={e => setIssueDraft(d => ({ ...d, reporter: e.target.value }))} />
            <input className={inputCls} placeholder="Assignee" value={issueDraft.assignee} onChange={e => setIssueDraft(d => ({ ...d, assignee: e.target.value }))} />
            <div className="col-span-2 flex justify-end">
              <button onClick={saveIssue} className="px-4 py-2 rounded-lg text-sm font-medium text-white" style={{ backgroundColor: TIFFANY }}>
                {editId ? "Update Issue" : "Add Issue"}
              </button>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-wrap gap-2 mb-3">
          <select className={`${inputCls} w-auto`} value={issueFilter.status} onChange={e => setIssueFilter(f => ({ ...f, status: e.target.value }))}>
            <option value="">All Statuses</option><option value="open">Open</option><option value="in_progress">In Progress</option><option value="resolved">Resolved</option><option value="closed">Closed</option>
          </select>
          <select className={`${inputCls} w-auto`} value={issueFilter.priority} onChange={e => setIssueFilter(f => ({ ...f, priority: e.target.value }))}>
            <option value="">All Priorities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
          </select>
          <input className={`${inputCls} w-auto min-w-[200px]`} placeholder="Search issues..." value={issueFilter.q} onChange={e => setIssueFilter(f => ({ ...f, q: e.target.value }))} />
          <select className={`${inputCls} w-auto`} value={issueSort} onChange={e => setIssueSort(e.target.value as typeof issueSort)}>
            <option value="priority">Sort: Priority</option><option value="date">Sort: Date</option><option value="status">Sort: Status</option>
          </select>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-slate-700">
              <th className="py-2 pr-2">Prio</th><th className="py-2 pr-2">Title</th><th className="py-2 pr-2">Status</th>
              <th className="py-2 pr-2">Assignee</th><th className="py-2 pr-2">Source</th><th className="py-2 pr-2">Created</th><th className="py-2">Actions</th>
            </tr></thead>
            <tbody>
              {filteredIssues.map(i => (
                <tr key={i.id} className="border-b border-gray-100 dark:border-slate-700/50 hover:bg-gray-50 dark:hover:bg-slate-700/30">
                  <td className="py-2 pr-2"><span className={`inline-block w-2.5 h-2.5 rounded-full ${PRIORITY_COLOR[i.priority]}`} title={i.priority} /></td>
                  <td className="py-2 pr-2 font-medium text-gray-900 dark:text-white max-w-[280px] truncate">{i.title}</td>
                  <td className="py-2 pr-2"><span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[i.status]}`}>{i.status.replace("_", " ")}</span></td>
                  <td className="py-2 pr-2 text-gray-600 dark:text-gray-300">{i.assignee}</td>
                  <td className="py-2 pr-2 text-gray-500 dark:text-gray-400">{i.source.replace("_", " ")}</td>
                  <td className="py-2 pr-2 text-gray-500 dark:text-gray-400">{fmtDate(i.created_at)}</td>
                  <td className="py-2 flex gap-1">
                    <button onClick={() => startEdit(i)} className="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-slate-600">Edit</button>
                    {i.status !== "resolved" && i.status !== "closed" && (
                      <button onClick={() => resolveIssue(i.id)} className="text-xs px-2 py-1 rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 hover:bg-green-200">Resolve</button>
                    )}
                    <button onClick={() => deleteIssue(i.id)} className="text-xs px-2 py-1 rounded bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 hover:bg-red-200">Delete</button>
                  </td>
                </tr>
              ))}
              {filteredIssues.length === 0 && (
                <tr><td colSpan={7} className="py-8 text-center text-gray-400">No issues match filters</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* S4: Feedback Inbox */}
      <div className={cardCls}>
        <div className="flex items-center justify-between mb-4">
          <h2 className={headCls}>User Feedback Inbox</h2>
          <button onClick={() => setShowFbForm(!showFbForm)} className="px-4 py-2 rounded-lg text-sm font-medium text-white" style={{ backgroundColor: TIFFANY }}>
            {showFbForm ? "Cancel" : "Add Feedback"}
          </button>
        </div>

        {showFbForm && (
          <div className="bg-gray-50 dark:bg-slate-700 border border-gray-200 dark:border-slate-600 rounded-lg p-4 mb-4 grid grid-cols-2 gap-3">
            <input className={inputCls} placeholder="User email" value={fbDraft.user_email} onChange={e => setFbDraft(d => ({ ...d, user_email: e.target.value }))} />
            <select className={inputCls} value={fbDraft.category} onChange={e => setFbDraft(d => ({ ...d, category: e.target.value as Feedback["category"] }))}>
              <option value="bug">Bug</option><option value="feature_request">Feature Request</option><option value="improvement">Improvement</option><option value="question">Question</option><option value="praise">Praise</option>
            </select>
            <input className={`${inputCls} col-span-2`} placeholder="Subject" value={fbDraft.subject} onChange={e => setFbDraft(d => ({ ...d, subject: e.target.value }))} />
            <textarea className={`${inputCls} col-span-2`} rows={3} placeholder="Message" value={fbDraft.message} onChange={e => setFbDraft(d => ({ ...d, message: e.target.value }))} />
            <div className="col-span-2 flex justify-end">
              <button onClick={saveFeedback} className="px-4 py-2 rounded-lg text-sm font-medium text-white" style={{ backgroundColor: TIFFANY }}>Save Feedback</button>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex gap-2 mb-3">
          <select className={`${inputCls} w-auto`} value={fbFilter.category} onChange={e => setFbFilter(f => ({ ...f, category: e.target.value }))}>
            <option value="">All Categories</option><option value="bug">Bug</option><option value="feature_request">Feature Request</option><option value="improvement">Improvement</option><option value="question">Question</option><option value="praise">Praise</option>
          </select>
          <select className={`${inputCls} w-auto`} value={fbFilter.status} onChange={e => setFbFilter(f => ({ ...f, status: e.target.value }))}>
            <option value="">All Statuses</option><option value="new">New</option><option value="reviewed">Reviewed</option><option value="actioned">Actioned</option><option value="archived">Archived</option>
          </select>
        </div>

        {/* Cards */}
        <div className="space-y-3">
          {filteredFb.map(f => (
            <div key={f.id} className="border border-gray-200 dark:border-slate-600 rounded-lg p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-slate-700/40 transition-colors"
              onClick={() => setExpandedFb(expandedFb === f.id ? null : f.id)}>
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${FB_CAT_CHIP[f.category]}`}>{f.category.replace("_", " ")}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${FB_STATUS_BADGE[f.status]}`}>{f.status}</span>
              </div>
              <p className="font-medium text-gray-900 dark:text-white">{f.subject}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400 line-clamp-2">{f.message}</p>
              <div className="flex items-center gap-3 mt-2 text-xs text-gray-400 dark:text-gray-500">
                <span>{f.user_email}</span><span>{fmtDate(f.created_at)}</span>
              </div>

              {expandedFb === f.id && (
                <div className="mt-3 pt-3 border-t border-gray-200 dark:border-slate-600 space-y-3" onClick={e => e.stopPropagation()}>
                  <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{f.message}</p>
                  <div>
                    <label className="text-xs font-medium text-gray-500 dark:text-gray-400 block mb-1">Internal Notes</label>
                    <textarea className={inputCls} rows={2} value={f.notes} onChange={e => updateFbNotes(f.id, e.target.value)} placeholder="Add internal notes..." />
                  </div>
                  <div className="flex items-center gap-2">
                    <select className={`${inputCls} w-auto`} value={f.status} onChange={e => updateFbStatus(f.id, e.target.value as Feedback["status"])}>
                      <option value="new">New</option><option value="reviewed">Reviewed</option><option value="actioned">Actioned</option><option value="archived">Archived</option>
                    </select>
                    <button onClick={() => convertToIssue(f)} className="px-3 py-2 rounded-lg text-xs font-medium text-white" style={{ backgroundColor: TIFFANY }}>
                      Convert to Issue
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
          {filteredFb.length === 0 && (
            <p className="py-8 text-center text-gray-400">No feedback matches filters</p>
          )}
        </div>
      </div>

      {/* S5: Deploy History */}
      <div className={cardCls}>
        <h2 className={`${headCls} mb-3`}>Deploy History</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-slate-700">
              <th className="py-2 pr-3">Version</th><th className="py-2 pr-3">Date</th><th className="py-2 pr-3">Status</th><th className="py-2 pr-3">Duration</th><th className="py-2">Changes</th>
            </tr></thead>
            <tbody>
              {deploys.map(d => (
                <tr key={d.version} className="border-b border-gray-100 dark:border-slate-700/50">
                  <td className="py-2 pr-3 font-mono text-gray-900 dark:text-white">{d.version}</td>
                  <td className="py-2 pr-3 text-gray-500 dark:text-gray-400">{d.date}</td>
                  <td className="py-2 pr-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${d.status === "Success" ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"}`}>{d.status}</span>
                  </td>
                  <td className="py-2 pr-3 text-gray-500 dark:text-gray-400 font-mono">{d.duration}</td>
                  <td className="py-2 text-gray-700 dark:text-gray-300">{d.changes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
