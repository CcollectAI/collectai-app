import React, { useEffect, useMemo, useState } from "react";

const API_BASE: string = (window as any).API_BASE || "http://localhost:8080";
const LOG_ACTUAL_URL: string = (window as any).LOG_ACTUAL_URL || "";
const EDGE_SECRET: string | undefined = (window as any).EDGE_SECRET;
const ADMIN_SECRET: string | undefined = (window as any).ADMIN_SECRET;

type ModelRow = { category: string; version: string; status: string; artifact_uri?: string };
type CountsRow = { category: string; model_version: string; day: string; n: number };
type MaeRow = { category: string; model_version: string; mae: number | null; n: number };

async function fetchJSON(path: string) {
  const headers: Record<string,string> = {};
  if (ADMIN_SECRET) headers["x-admin-secret"] = ADMIN_SECRET;
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}
async function post(path: string, method="POST") {
  const headers: Record<string,string> = {};
  if (ADMIN_SECRET) headers["x-admin-secret"] = ADMIN_SECRET;
  const res = await fetch(`${API_BASE}${path}`, { method, headers });
  const txt = await res.text();
  if (!res.ok) throw new Error(txt || `${res.status} ${res.statusText}`);
  try { return JSON.parse(txt); } catch { return { ok: true, raw: txt }; }
}

export default function Admin() {
  const [loading, setLoading] = useState(false);
  const [models, setModels] = useState<ModelRow[]>([]);
  const [counts, setCounts] = useState<CountsRow[]>([]);
  const [mae, setMae] = useState<MaeRow[]>([]);
  const [msg, setMsg] = useState<string>("");

  const categories = useMemo(() => {
    const set = new Set(models.map(m => m.category));
    counts.forEach(c => set.add(c.category));
    mae.forEach(m => set.add(m.category));
    return Array.from(set).sort();
  }, [models, counts, mae]);

  async function load() {
    setLoading(true); setMsg("");
    try {
      const [mods, metrics] = await Promise.all([
        fetchJSON("/admin/models"),
        fetchJSON("/admin/metrics"),
      ]);
      setModels(mods);
      setCounts(metrics.counts_7d || []);
      setMae(metrics.mae || []);
    } catch (e:any) {
      setMsg(`Load failed: ${e.message}`);
    } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function activateBest(category: string) {
    try {
      setMsg("");
      const j = await post(`/admin/activate_best?category=${encodeURIComponent(category)}`);
      setMsg(`Activated ${category}: ${(j.activated||"?")}`);
      await load();
    } catch(e:any) {
      setMsg(`Activate failed: ${e.message}`);
    }
  }
  async function reloadCategory(category: string) {
    try {
      setMsg("");
      await post(`/admin/reload?category=${encodeURIComponent(category)}`);
      setMsg(`Reloaded cache for ${category}`);
    } catch(e:any) {
      setMsg(`Reload failed: ${e.message}`);
    }
  }
  async function trainNow(category?: string) {
    try {
      setMsg("");
      const q = category ? `?category=${encodeURIComponent(category)}&min_rows=150` : `?min_rows=150`;
      const j = await post(`/admin/train_now${q}`);
      setMsg(`Train started (${category||"all"}): pid=${j.pid||"?"}`);
    } catch(e:any) {
      setMsg(`Train failed: ${e.message}`);
    }
  }

  function MaeCell({ cat, ver }: { cat: string; ver: string }) {
    const row = mae.find(m => m.category === cat && m.model_version === ver);
    if (!row) return <span className="text-gray-400">—</span>;
    return <span className="font-medium">{row.mae !== null ? row.mae.toFixed(2) : "—"}</span>;
  }
  function CountCell({ cat, ver }: { cat: string; ver: string }) {
    const total = counts.filter(c => c.category === cat && c.model_version === ver)
      .reduce((a, b) => a + (b.n || 0), 0);
    return <span>{total || 0}</span>;
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">CollectAI • Admin</h1>
          <div className="flex items-center gap-2">
            <button onClick={load} className="px-3 py-2 rounded-xl bg-gray-900 text-white text-sm">Refresh</button>
            {loading && <span className="text-sm text-gray-500">Loading…</span>}
          </div>
        </header>

        {!!msg && (<div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-sm break-all">{msg}</div>)}

        {/* Retrain Now */}
        <section className="grid grid-cols-1 gap-4">
          <div className="bg-white rounded-2xl shadow p-4">
            <h2 className="text-lg font-semibold mb-3">Retrain Now</h2>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => trainNow()} className="px-3 py-2 rounded-xl bg-emerald-600 text-white">All Categories</button>
              {categories.map(cat => (
                <button key={cat} onClick={() => trainNow(cat)} className="px-3 py-2 rounded-xl bg-gray-200 hover:bg-gray-300">{cat}</button>
              ))}
            </div>
          </div>
        </section>

        {/* Active Models */}
        <section className="grid grid-cols-1 gap-4">
          <div className="bg-white rounded-2xl shadow p-4">
            <h2 className="text-lg font-semibold mb-3">Active Models</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500">
                    <th className="py-2 pr-4">Category</th>
                    <th className="py-2 pr-4">Version</th>
                    <th className="py-2 pr-4">MAE</th>
                    <th className="py-2 pr-4">7d Count</th>
                    <th className="py-2 pr-4">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((m) => (
                    <tr key={`${m.category}:${m.version}`} className="border-t border-gray-100">
                      <td className="py-2 pr-4 font-medium">{m.category}</td>
                      <td className="py-2 pr-4">{m.version}</td>
                      <td className="py-2 pr-4"><MaeCell cat={m.category} ver={m.version} /></td>
                      <td className="py-2 pr-4"><CountCell cat={m.category} ver={m.version} /></td>
                      <td className="py-2 pr-4 space-x-2">
                        <button onClick={() => reloadCategory(m.category)} className="px-3 py-1.5 rounded-lg bg-gray-200 hover:bg-gray-300">Reload</button>
                        <button onClick={() => activateBest(m.category)} className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">Activate Best</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* MAE Leaderboard */}
        <section className="grid grid-cols-1 gap-4">
          <div className="bg-white rounded-2xl shadow p-4">
            <h2 className="text-lg font-semibold mb-3">MAE Leaderboard</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500">
                    <th className="py-2 pr-4">Category</th>
                    <th className="py-2 pr-4">Version</th>
                    <th className="py-2 pr-4">MAE</th>
                    <th className="py-2 pr-4">Samples</th>
                  </tr>
                </thead>
                <tbody>
                  {mae.map((r) => (
                    <tr key={`${r.category}:${r.model_version}`} className="border-t border-gray-100">
                      <td className="py-2 pr-4">{r.category}</td>
                      <td className="py-2 pr-4">{r.model_version}</td>
                      <td className="py-2 pr-4">{r.mae !== null ? r.mae.toFixed(2) : "—"}</td>
                      <td className="py-2 pr-4">{r.n}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* Log Actual */}
        <section className="grid grid-cols-1 gap-4">
          <div className="bg-white rounded-2xl shadow p-4">
            <h2 className="text-lg font-semibold mb-3">Log Actual (populate MAE)</h2>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const id = Number((document.getElementById("gt-id") as HTMLInputElement).value);
                const val = Number((document.getElementById("gt-actual") as HTMLInputElement).value);
                try {
                  const res = await fetch(LOG_ACTUAL_URL, {
                    method: "POST",
                    headers: {
                      "Content-Type": "application/json",
                      "Authorization": `Bearer ${(window as any).SUPABASE_ANON_KEY || ""}`,
                      ...(EDGE_SECRET ? { "x-edge-secret": EDGE_SECRET } : {})
                    },
                    body: JSON.stringify({ id, actual_eur: val }),
                  });
                  const j = await res.json().catch(() => ({}));
                  alert(res.ok ? `Logged: ${JSON.stringify(j)}` : `Failed: ${res.status} ${res.statusText} ${JSON.stringify(j)}`);
                } catch (err:any) {
                  alert(`Error: ${err.message}`);
                }
              }}
              className="flex flex-wrap items-end gap-3"
            >
              <label className="flex flex-col">
                <span className="text-sm text-gray-600">prediction_event id</span>
                <input id="gt-id" type="number" className="border rounded-lg px-3 py-2" required />
              </label>
              <label className="flex flex-col">
                <span className="text-sm text-gray-600">actual_eur</span>
                <input id="gt-actual" type="number" step="0.01" className="border rounded-lg px-3 py-2" required />
              </label>
              <button type="submit" className="px-3 py-2 rounded-xl bg-emerald-600 text-white">Submit</button>
            </form>
          </div>
        </section>

      </div>
    </div>
  );
}
