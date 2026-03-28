"use client";

import { useEffect, useState, useCallback } from "react";
import { getSupabase, isSupabaseConfigured } from "@/lib/supabase";

interface Creator {
  id?: string;
  name: string;
  handle: string;
  platform: string;
  language: string;
  affiliate_code: string;
  is_active: boolean;
  kits_sent: number;
  cogs_per_kit_cents: number;
  affiliate_payout_pct: number;
}

const EMPTY_CREATOR: Creator = {
  name: "",
  handle: "",
  platform: "tiktok",
  language: "en",
  affiliate_code: "",
  is_active: true,
  kits_sent: 2,
  cogs_per_kit_cents: 600,
  affiliate_payout_pct: 15,
};

const LANGUAGES = ["en", "de", "fr", "es", "it", "nl"] as const;
const PLATFORMS = ["tiktok", "instagram", "youtube"] as const;

export function AdminCreatorManager() {
  const [creators, setCreators] = useState<Creator[]>([]);
  const [editing, setEditing] = useState<Creator | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const configured = isSupabaseConfigured();

  const load = useCallback(async () => {
    if (!configured) return;
    const sb = getSupabase();
    if (!sb) return;

    const { data } = await sb
      .from("creators")
      .select("*")
      .order("name");

    if (data) setCreators(data);
  }, [configured]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async () => {
    if (!editing || !configured) return;
    const sb = getSupabase();
    if (!sb) return;

    setSaving(true);
    setMessage("");

    try {
      if (editing.id) {
        const { error } = await sb
          .from("creators")
          .update({
            name: editing.name,
            handle: editing.handle,
            platform: editing.platform,
            language: editing.language,
            affiliate_code: editing.affiliate_code,
            is_active: editing.is_active,
            kits_sent: editing.kits_sent,
            cogs_per_kit_cents: editing.cogs_per_kit_cents,
            affiliate_payout_pct: editing.affiliate_payout_pct,
          })
          .eq("id", editing.id);

        if (error) throw error;
        setMessage("Creator updated.");
      } else {
        const { error } = await sb.from("creators").insert({
          name: editing.name,
          handle: editing.handle,
          platform: editing.platform,
          language: editing.language,
          affiliate_code: editing.affiliate_code,
          is_active: editing.is_active,
          kits_sent: editing.kits_sent,
          cogs_per_kit_cents: editing.cogs_per_kit_cents,
          affiliate_payout_pct: editing.affiliate_payout_pct,
        });

        if (error) throw error;
        setMessage("Creator added.");
      }

      setEditing(null);
      await load();
    } catch (err) {
      setMessage(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSaving(false);
    }
  };

  if (!configured) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-md p-4">
        <p className="text-sm text-amber-800">
          <span className="font-semibold">Supabase required.</span> Connect
          Supabase to manage creators. Creators are stored in the{" "}
          <code className="bg-amber-100 px-1 rounded text-xs">creators</code>{" "}
          table.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-[#0D1B2A]">Creator Manager</h3>
        <button
          type="button"
          onClick={() => setEditing({ ...EMPTY_CREATOR })}
          className="px-4 py-2 text-sm font-medium bg-[#0D1B2A] text-white rounded-lg hover:bg-[#1a2d42] transition-colors"
        >
          + Add Creator
        </button>
      </div>

      {message && (
        <p className={`text-sm ${message.startsWith("Error") ? "text-red-600" : "text-emerald-600"}`}>
          {message}
        </p>
      )}

      {/* Creator list */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse border border-gray-300 text-sm">
          <thead>
            <tr className="bg-gray-50">
              <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Name</th>
              <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Handle</th>
              <th className="border border-gray-300 px-3 py-2 text-center font-semibold text-gray-700">Platform</th>
              <th className="border border-gray-300 px-3 py-2 text-center font-semibold text-gray-700">Lang</th>
              <th className="border border-gray-300 px-3 py-2 text-center font-semibold text-gray-700">Code</th>
              <th className="border border-gray-300 px-3 py-2 text-center font-semibold text-gray-700">Status</th>
              <th className="border border-gray-300 px-3 py-2 text-center font-semibold text-gray-700">Kits Sent</th>
              <th className="border border-gray-300 px-3 py-2 text-center font-semibold text-gray-700">Payout %</th>
              <th className="border border-gray-300 px-3 py-2 text-center font-semibold text-gray-700">Actions</th>
            </tr>
          </thead>
          <tbody>
            {creators.map((c) => (
              <tr key={c.id || c.affiliate_code} className="hover:bg-gray-50">
                <td className="border border-gray-300 px-3 py-2 font-medium text-gray-900">{c.name}</td>
                <td className="border border-gray-300 px-3 py-2 text-gray-600">{c.handle}</td>
                <td className="border border-gray-300 px-3 py-2 text-center text-xs">
                  <span className="inline-block px-2 py-0.5 bg-gray-100 rounded">{c.platform}</span>
                </td>
                <td className="border border-gray-300 px-3 py-2 text-center">
                  <span className="inline-block px-1.5 py-0.5 bg-blue-50 text-[#0D1B2A] rounded text-xs font-medium">
                    {c.language?.toUpperCase()}
                  </span>
                </td>
                <td className="border border-gray-300 px-3 py-2 text-center">
                  <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">{c.affiliate_code}</code>
                </td>
                <td className="border border-gray-300 px-3 py-2 text-center">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                    c.is_active ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
                  }`}>
                    {c.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="border border-gray-300 px-3 py-2 text-center">{c.kits_sent}</td>
                <td className="border border-gray-300 px-3 py-2 text-center">{c.affiliate_payout_pct}%</td>
                <td className="border border-gray-300 px-3 py-2 text-center">
                  <button
                    type="button"
                    onClick={() => setEditing({ ...c })}
                    className="text-xs font-medium text-[#0D1B2A] hover:underline"
                  >
                    Edit
                  </button>
                </td>
              </tr>
            ))}
            {creators.length === 0 && (
              <tr>
                <td colSpan={9} className="border border-gray-300 px-3 py-6 text-center text-gray-400">
                  No creators yet. Click &quot;+ Add Creator&quot; to onboard your first creator.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Edit / Add form */}
      {editing && (
        <div className="border border-gray-200 rounded-lg p-6 bg-white">
          <h4 className="text-sm font-bold text-[#0D1B2A] mb-4">
            {editing.id ? "Edit Creator" : "Add Creator"}
          </h4>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Name</label>
              <input
                type="text"
                value={editing.name}
                onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                placeholder="Luna Craft"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Handle</label>
              <input
                type="text"
                value={editing.handle}
                onChange={(e) => setEditing({ ...editing, handle: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                placeholder="@lunacraft_de"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Platform</label>
              <select
                value={editing.platform}
                onChange={(e) => setEditing({ ...editing, platform: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                {PLATFORMS.map((p) => (
                  <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Language</label>
              <select
                value={editing.language}
                onChange={(e) => setEditing({ ...editing, language: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                {LANGUAGES.map((l) => (
                  <option key={l} value={l}>{l.toUpperCase()}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Affiliate Code</label>
              <input
                type="text"
                value={editing.affiliate_code}
                onChange={(e) => setEditing({ ...editing, affiliate_code: e.target.value.toUpperCase() })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono"
                placeholder="DE-LUNA-DESKBUDDY1"
              />
              <p className="text-[10px] text-gray-400 mt-0.5">Format: LANG-NAME-DROP</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Kits Sent</label>
              <input
                type="number"
                value={editing.kits_sent}
                onChange={(e) => setEditing({ ...editing, kits_sent: parseInt(e.target.value) || 0 })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                min={0}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">COGS per Kit (cents)</label>
              <input
                type="number"
                value={editing.cogs_per_kit_cents}
                onChange={(e) => setEditing({ ...editing, cogs_per_kit_cents: parseInt(e.target.value) || 600 })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                min={0}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Affiliate Payout %</label>
              <input
                type="number"
                value={editing.affiliate_payout_pct}
                onChange={(e) => setEditing({ ...editing, affiliate_payout_pct: parseInt(e.target.value) || 15 })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                min={0}
                max={100}
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-gray-600">Active</label>
              <button
                type="button"
                onClick={() => setEditing({ ...editing, is_active: !editing.is_active })}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  editing.is_active ? "bg-emerald-500" : "bg-gray-300"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
                    editing.is_active ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>
          </div>

          <div className="flex gap-3 mt-6">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !editing.name || !editing.affiliate_code}
              className="px-4 py-2 text-sm font-medium bg-[#FF6B6B] text-white rounded-lg hover:bg-[#e55a5a] transition-colors disabled:opacity-50"
            >
              {saving ? "Saving..." : editing.id ? "Update" : "Add Creator"}
            </button>
            <button
              type="button"
              onClick={() => { setEditing(null); setMessage(""); }}
              className="px-4 py-2 text-sm font-medium bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
