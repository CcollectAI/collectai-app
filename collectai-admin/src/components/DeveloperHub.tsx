"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { getSupabase } from "@/lib/supabase";

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

/* ───────────────────────── Constants ───────────────────── */

const TIFFANY = "#81D8D0";
const LS_ISSUES = "dev-issues";
const LS_FEEDBACK = "dev-feedback";


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

        // 3) Both empty — show empty. Never write a seed anywhere.
        setDataRaw(seed);
        initialized.current = true;
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
  // No seeds (2026-09-27): the hook used to show SEED_ISSUES / SEED_FEEDBACK —
  // invented users and bugs — when the table was empty, AND write them into
  // prod's admin_dev_hub, where all 10 were found as if real.
  const [issues, setIssues] = useSupabasePersisted<Issue>("issue", LS_ISSUES, []);
  const [feedback, setFeedback] = useSupabasePersisted<Feedback>("feedback", LS_FEEDBACK, []);

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

      {/* S1 (2026-09-27): eight hard-coded cards used to sit here — "3,194
          backend tests", "142 ms latency", "99.97% uptime", "0.12% error rate" —
          constants typed into this file, not measurements. */}
      <div className={cardCls}>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Engineering metrics are not connected: the server has no metrics, error-rate or deploy-history
          endpoint. Test counts live in CI; server errors in <code>/opt/collectors/bake.log</code> and the daily watchdog.
        </p>
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

    </div>
  );
}
