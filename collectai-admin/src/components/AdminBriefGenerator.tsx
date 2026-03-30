"use client";

import { useState } from "react";
import {
  fetchUGCDashboardData,
} from "@/lib/kpi";
import { AdminDemoBanner } from "@/components/AdminDemoBanner";
import type { UGCDashboardData } from "@/lib/kpi";
import {
  generateBrief,
  exportBriefMarkdown,
  exportBriefWhatsApp,
} from "@/lib/briefs";
import type { BriefTemplate } from "@/lib/briefs";

const KIT_OPTIONS = [
  "pokemon",
  "mtg",
  "funko",
  "sneakers",
  "watches",
  "vinyl",
  "lego",
  "yugioh",
  "kpop",
  "manga",
  "hot_toys",
  "warhammer",
];

const LANGUAGE_OPTIONS = ["DE", "FR", "NL", "EN", "ES", "IT"];

type TabKey = "preview" | "markdown" | "whatsapp";

export function AdminBriefGenerator() {
  const [selectedKit, setSelectedKit] = useState(KIT_OPTIONS[0]);
  const [selectedLang, setSelectedLang] = useState(LANGUAGE_OPTIONS[0]);
  const [brief, setBrief] = useState<BriefTemplate | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("preview");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleGenerate = async () => {
    setLoading(true);
    setBrief(null);
    try {
      const data: UGCDashboardData = await fetchUGCDashboardData(30);
      const result = generateBrief({
        kitSlug: selectedKit,
        podLanguage: selectedLang,
        topHooks: data.hookAnalysis,
        topFormats: data.formatAnalysis,
        topVideos: data.topPerformers,
      });
      setBrief(result);
      setActiveTab("preview");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-bold text-[#0D1B2A]">Creator Brief Generator</h2>
        <AdminDemoBanner />
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-gray-400">
            Kit
          </label>
          <select
            value={selectedKit}
            onChange={(e) => setSelectedKit(e.target.value)}
            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs"
          >
            {KIT_OPTIONS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-gray-400">
            Pod Language
          </label>
          <select
            value={selectedLang}
            onChange={(e) => setSelectedLang(e.target.value)}
            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs"
          >
            {LANGUAGE_OPTIONS.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={handleGenerate}
          disabled={loading}
          className="rounded-lg bg-[#0D1B2A] px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#1a2d42] disabled:opacity-50"
        >
          {loading ? "Generating..." : "Generate Brief"}
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-[#FF6B6B]" />
        </div>
      )}

      {/* Brief output */}
      {brief && !loading && (
        <div className="space-y-4">
          {/* Tabs */}
          <div className="flex gap-1 border-b border-gray-200">
            {(["preview", "markdown", "whatsapp"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-xs font-semibold capitalize transition ${
                  activeTab === tab
                    ? "border-b-2 border-[#0D1B2A] text-[#0D1B2A]"
                    : "text-gray-400 hover:text-gray-600"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Preview tab */}
          {activeTab === "preview" && (
            <div className="space-y-4">
              {/* Title bar */}
              <div className="rounded-xl bg-white p-5 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-[#0D1B2A]">{brief.title}</h3>
                    <p className="text-xs text-gray-400">
                      Created {brief.createdAt.slice(0, 10)} · Due {brief.dueDate} · {brief.platform}
                    </p>
                  </div>
                  <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[10px] font-bold uppercase text-gray-600">
                    {brief.status}
                  </span>
                </div>
              </div>

              {/* Objective */}
              <div className="rounded-xl bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">Objective</p>
                <p className="mt-2 text-sm text-[#0D1B2A]">{brief.objective}</p>
                <div className="mt-3 flex gap-3 text-xs text-gray-400">
                  <span>Format: <span className="font-semibold text-[#0D1B2A] capitalize">{brief.format}</span></span>
                  <span>Duration: <span className="font-semibold text-[#0D1B2A]">{brief.duration}</span></span>
                  <span>Aspect: <span className="font-semibold text-[#0D1B2A]">{brief.aspectRatio}</span></span>
                </div>
              </div>

              {/* Hook Options */}
              <div className="rounded-xl bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">Hook Options</p>
                <div className="mt-3 space-y-2">
                  {brief.hookOptions.map((hook, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#0D1B2A] text-[10px] font-bold text-white">
                        {i + 1}
                      </span>
                      <p className="text-sm font-medium text-[#0D1B2A]">&ldquo;{hook}&rdquo;</p>
                    </div>
                  ))}
                  {brief.hookOptions.length === 0 && (
                    <p className="text-xs text-gray-400">No hook data available yet. Add your own hooks.</p>
                  )}
                </div>
              </div>

              {/* Mood Board */}
              <div className="rounded-xl bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">Mood Board</p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {brief.moodBoard.map((item, i) => (
                    <div key={i} className="rounded-lg bg-gray-50 p-3">
                      <p className="text-xs text-[#0D1B2A]">{item}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Do's and Don'ts */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="rounded-xl bg-white p-5 shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-wider text-emerald-600">Do&apos;s</p>
                  <ul className="mt-3 space-y-2">
                    {brief.dosAndDonts.dos.map((item, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs text-[#0D1B2A]">
                        <span className="mt-0.5 text-emerald-500">&#10003;</span>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="rounded-xl bg-white p-5 shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-wider text-red-500">Don&apos;ts</p>
                  <ul className="mt-3 space-y-2">
                    {brief.dosAndDonts.donts.map((item, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs text-[#0D1B2A]">
                        <span className="mt-0.5 text-red-400">&#10007;</span>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Key Messages */}
              <div className="rounded-xl bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">Key Messages</p>
                <div className="mt-3 space-y-2">
                  {brief.keyMessages.map((msg, i) => (
                    <p key={i} className="text-sm font-medium text-[#0D1B2A]">&ldquo;{msg}&rdquo;</p>
                  ))}
                </div>
              </div>

              {/* Inspiration */}
              <div className="rounded-xl bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                  Inspiration (What&apos;s Working Now)
                </p>
                <div className="mt-3 space-y-2">
                  {brief.inspiration.map((item, i) => (
                    <div key={i} className="rounded-lg border border-gray-100 p-3">
                      <p className="text-xs text-[#0D1B2A]">{item}</p>
                    </div>
                  ))}
                  {brief.inspiration.length === 0 && (
                    <p className="text-xs text-gray-400">No top-performing videos found in this period.</p>
                  )}
                </div>
              </div>

              {/* Product Details & CTA */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="rounded-xl bg-white p-5 shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">Product Details</p>
                  <p className="mt-2 text-xs text-[#0D1B2A]">{brief.productDetails}</p>
                </div>
                <div className="rounded-xl bg-white p-5 shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">CTA</p>
                  <p className="mt-2 text-sm font-semibold text-[#0D1B2A]">{brief.cta}</p>
                </div>
              </div>
            </div>
          )}

          {/* Markdown tab */}
          {activeTab === "markdown" && (
            <div className="space-y-3">
              <div className="flex justify-end">
                <button
                  onClick={() => handleCopy(exportBriefMarkdown(brief))}
                  className="rounded-lg bg-gray-100 px-3 py-1.5 text-xs font-semibold text-gray-600 transition hover:bg-gray-200"
                >
                  {copied ? "Copied!" : "Copy to clipboard"}
                </button>
              </div>
              <pre className="overflow-x-auto rounded-xl border border-gray-200 bg-white p-5 text-xs leading-relaxed text-[#0D1B2A] whitespace-pre-wrap">
                {exportBriefMarkdown(brief)}
              </pre>
            </div>
          )}

          {/* WhatsApp tab */}
          {activeTab === "whatsapp" && (
            <div className="space-y-3">
              <div className="flex justify-end">
                <button
                  onClick={() => handleCopy(exportBriefWhatsApp(brief))}
                  className="rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-emerald-600"
                >
                  {copied ? "Copied!" : "Copy to clipboard"}
                </button>
              </div>
              <pre className="overflow-x-auto rounded-xl border border-gray-200 bg-[#ECE5DD] p-5 text-xs leading-relaxed text-[#0D1B2A] whitespace-pre-wrap">
                {exportBriefWhatsApp(brief)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
