"use client";

import { useState, useEffect, useCallback } from "react";
import { APP_CONFIG } from "../../../admin.config";

// Template components
import { AdminKPIDashboard } from "@/components/AdminKPIDashboard";
import { AdminUGCDashboard } from "@/components/AdminUGCDashboard";
import { AdminContentPipeline } from "@/components/AdminContentPipeline";
import { AdminPodManager } from "@/components/AdminPodManager";
import { AdminCreatorManager } from "@/components/AdminCreatorManager";
import { AdminBriefGenerator } from "@/components/AdminBriefGenerator";
import { AdminCommissionTracker } from "@/components/AdminCommissionTracker";
import { AdminWeeklyReport } from "@/components/AdminWeeklyReport";
import { AdminSwipeFile } from "@/components/AdminSwipeFile";
import { AdminAccountTracker } from "@/components/AdminAccountTracker";
import { AdminBoostTracker } from "@/components/AdminBoostTracker";

// CollectAI-specific components
import { CollectAIOverview } from "@/components/CollectAIOverview";
import { AdminMLModels } from "@/components/AdminMLModels";
import { AdminWorkerHealth } from "@/components/AdminWorkerHealth";
import { AdminDemandSignals } from "@/components/AdminDemandSignals";
import { AdminUserManager } from "@/components/AdminUserManager";
import { AdminSponsorAnalytics } from "@/components/AdminSponsorAnalytics";

// Intelligence & Automation
import { IntelligenceTab } from "@/components/IntelligenceTab";
import { AutoBriefScheduler } from "@/components/AutoBriefScheduler";
import { PipelineAutomation } from "@/components/PipelineAutomation";
import { DigestScheduler } from "@/components/DigestScheduler";

// ─── Navigation structure ───────────────────────────────────────────────────

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  shortcut?: string;
  moduleKey?: string;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const IC = "h-4 w-4";

const NAV: NavGroup[] = [
  {
    title: "Platform",
    items: [
      {
        id: "overview", label: "Overview", shortcut: "1", moduleKey: "overview",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>,
      },
      {
        id: "users", label: "Users", shortcut: "2", moduleKey: "userManager",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>,
      },
      {
        id: "kpi", label: "KPI Funnel", shortcut: "3", moduleKey: "kpiDashboard",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>,
      },
      {
        id: "sponsors", label: "Sponsors", moduleKey: "sponsorAnalytics",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
      },
    ],
  },
  {
    title: "Intelligence",
    items: [
      {
        id: "ml-models", label: "ML Models", shortcut: "4", moduleKey: "mlModels",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>,
      },
      {
        id: "workers", label: "Worker Health", shortcut: "5", moduleKey: "workerHealth",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" /></svg>,
      },
      {
        id: "demand", label: "Demand Signals", shortcut: "6", moduleKey: "demandSignals",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>,
      },
    ],
  },
  {
    title: "Content Marketing",
    items: [
      {
        id: "ugc", label: "UGC Analytics", moduleKey: "ugcAnalytics",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>,
      },
      {
        id: "accounts", label: "Social Accounts", moduleKey: "accounts",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" /></svg>,
      },
      {
        id: "boost", label: "Spark Ads", moduleKey: "sparkAds",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>,
      },
      {
        id: "swipefile", label: "Swipe File", moduleKey: "swipeFile",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" /></svg>,
      },
      {
        id: "pipeline", label: "Pipeline", moduleKey: "pipeline",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" /></svg>,
      },
      {
        id: "pods", label: "Category Pods", moduleKey: "pods",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>,
      },
      {
        id: "creators", label: "Creators", moduleKey: "creators",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>,
      },
      {
        id: "briefs", label: "Brief Generator", moduleKey: "briefGenerator",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>,
      },
      {
        id: "commissions", label: "Commissions", moduleKey: "commissions",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" /></svg>,
      },
      {
        id: "reports", label: "Weekly Reports", moduleKey: "weeklyReports",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>,
      },
    ],
  },
  {
    title: "Automation",
    items: [
      {
        id: "intelligence", label: "Intelligence",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>,
      },
      {
        id: "auto-briefs", label: "Auto Briefs",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>,
      },
      {
        id: "pipeline-auto", label: "Pipeline Rules",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>,
      },
      {
        id: "digests", label: "Digest Scheduler",
        icon: <svg className={IC} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>,
      },
    ],
  },
];

// Filter nav items based on module toggles
function getFilteredNav(): NavGroup[] {
  const modules = APP_CONFIG.modules as Record<string, boolean>;
  return NAV.map((group) => ({
    ...group,
    items: group.items.filter((item) => {
      if (!item.moduleKey) return true;
      return modules[item.moduleKey] !== false;
    }),
  })).filter((group) => group.items.length > 0);
}

type TabId = string;

interface AdminTabsProps {
  kits: unknown[];
}

export function AdminTabs({ kits: _kits }: AdminTabsProps) {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const filteredNav = getFilteredNav();

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!e.ctrlKey && !e.metaKey) return;
    for (const group of filteredNav) {
      for (const item of group.items) {
        if (item.shortcut && e.key === item.shortcut) {
          e.preventDefault();
          setActiveTab(item.id);
          setMobileMenuOpen(false);
        }
      }
    }
  }, [filteredNav]);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // Close mobile menu on resize to desktop
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const handler = () => { if (mq.matches) setMobileMenuOpen(false); };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  function selectTab(id: string) {
    setActiveTab(id);
    setMobileMenuOpen(false);
  }

  const sidebarContent = (
    <nav className="p-2 space-y-4 overflow-y-auto max-h-[calc(100vh-7rem)]">
      {filteredNav.map((group) => (
        <div key={group.title}>
          <p className="mb-1.5 px-2 text-[9px] font-bold uppercase tracking-widest text-gray-400 dark:text-gray-500">
            {group.title}
          </p>
          <div className="space-y-0.5">
            {group.items.map((item) => {
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => selectTab(item.id)}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium transition-all ${
                    isActive
                      ? "bg-[#81D8D0] text-white shadow-sm"
                      : "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-slate-700 hover:text-gray-700 dark:hover:text-gray-200"
                  }`}
                >
                  <span className="flex-shrink-0">{item.icon}</span>
                  <span className="flex-1 truncate">{item.label}</span>
                  {item.shortcut && (
                    <kbd className={`hidden text-[9px] font-mono lg:inline ${isActive ? "text-white/50" : "text-gray-300 dark:text-gray-600"}`}>
                      {"\u2318"}{item.shortcut}
                    </kbd>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );

  return (
    <div className="flex min-h-[calc(100vh-4rem)] print:block">
      {/* Mobile hamburger bar */}
      <div className="md:hidden sticky top-[52px] z-20 flex items-center gap-3 border-b border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 py-2 print:hidden">
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="rounded-lg bg-gray-100 dark:bg-slate-700 p-2 text-gray-600 dark:text-gray-300"
          aria-label="Toggle menu"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={mobileMenuOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"} />
          </svg>
        </button>
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
          {filteredNav.flatMap(g => g.items).find(i => i.id === activeTab)?.label ?? "Overview"}
        </span>
      </div>

      {/* Mobile overlay */}
      {mobileMenuOpen && (
        <div
          className="md:hidden fixed inset-0 z-30 bg-black/30 backdrop-blur-sm"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Mobile slide-out sidebar */}
      <aside
        className={`md:hidden fixed top-0 left-0 z-40 h-full w-64 bg-white dark:bg-slate-800 border-r border-gray-200 dark:border-slate-700 shadow-xl transition-transform duration-200 print:hidden ${
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-12 items-center justify-between border-b border-gray-100 dark:border-slate-700 px-4">
          <span className="text-xs font-bold text-gray-900 dark:text-white">Navigation</span>
          <button onClick={() => setMobileMenuOpen(false)} className="text-gray-400 hover:text-gray-600">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        {sidebarContent}
      </aside>

      {/* Desktop sidebar */}
      <aside
        className={`hidden md:block flex-shrink-0 border-r border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 transition-all duration-200 print:hidden ${
          sidebarOpen ? "w-52" : "w-14"
        }`}
      >
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="flex h-10 w-full items-center justify-center border-b border-gray-100 dark:border-slate-700 text-gray-400 dark:text-gray-500 transition hover:text-gray-600 dark:hover:text-gray-300"
          aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={sidebarOpen ? "M11 19l-7-7 7-7m8 14l-7-7 7-7" : "M13 5l7 7-7 7M5 5l7 7-7 7"} />
          </svg>
        </button>

        {sidebarOpen ? (
          sidebarContent
        ) : (
          <nav className="p-1 space-y-0.5 overflow-y-auto max-h-[calc(100vh-7rem)]">
            {filteredNav.flatMap((group) =>
              group.items.map((item) => {
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => selectTab(item.id)}
                    title={`${item.label}${item.shortcut ? ` (\u2318${item.shortcut})` : ""}`}
                    className={`flex w-full items-center justify-center rounded-lg p-2.5 transition-all ${
                      isActive
                        ? "bg-[#81D8D0] text-white shadow-sm"
                        : "text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-slate-700 hover:text-gray-600"
                    }`}
                  >
                    {item.icon}
                  </button>
                );
              })
            )}
          </nav>
        )}
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-4 md:p-6 print:p-0 transition-colors">
        {activeTab === "overview" && <CollectAIOverview />}
        {activeTab === "users" && <AdminUserManager />}
        {activeTab === "kpi" && <AdminKPIDashboard />}
        {activeTab === "sponsors" && <AdminSponsorAnalytics />}
        {activeTab === "ml-models" && <AdminMLModels />}
        {activeTab === "workers" && <AdminWorkerHealth />}
        {activeTab === "demand" && <AdminDemandSignals />}
        {activeTab === "ugc" && <AdminUGCDashboard />}
        {activeTab === "accounts" && <AdminAccountTracker />}
        {activeTab === "boost" && <AdminBoostTracker />}
        {activeTab === "swipefile" && <AdminSwipeFile />}
        {activeTab === "pipeline" && <AdminContentPipeline />}
        {activeTab === "pods" && <AdminPodManager />}
        {activeTab === "creators" && <AdminCreatorManager />}
        {activeTab === "briefs" && <AdminBriefGenerator />}
        {activeTab === "commissions" && <AdminCommissionTracker />}
        {activeTab === "reports" && <AdminWeeklyReport />}
        {activeTab === "intelligence" && <IntelligenceTab />}
        {activeTab === "auto-briefs" && <AutoBriefScheduler />}
        {activeTab === "pipeline-auto" && <PipelineAutomation />}
        {activeTab === "digests" && <DigestScheduler />}
      </main>
    </div>
  );
}
