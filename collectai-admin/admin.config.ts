// ═══════════════════════════════════════════════════════════════════════════
// COLLECTAI ADMIN DASHBOARD CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════

export const APP_CONFIG = {
  // ─── Branding ──────────────────────────────────────────────────────────
  name: "CollectAI",
  shortName: "C",
  tagline: "Admin Dashboard — Collectibles Intelligence",
  domain: "collectai.app",
  contactEmail: "hello@collectai.app",

  // ─── Colors ────────────────────────────────────────────────────────────
  colors: {
    primary: "#81D8D0",      // Tiffany Blue
    primaryDark: "#5FBFB6",  // Hover state
    secondary: "#1E3A8A",    // Navy charts/headers
    navy: "#0D1B2A",         // Dark text / sidebar
    text: "#333333",         // Body text
    success: "#10B981",      // Green accents
    warning: "#F59E0B",      // Amber alerts
    danger: "#EF4444",       // Red errors
  },

  // ─── Auth ──────────────────────────────────────────────────────────────
  adminPin: "2026",          // Override with NEXT_PUBLIC_ADMIN_PIN env var

  // ─── Backend API ───────────────────────────────────────────────────────
  api: {
    baseUrl: process.env.NEXT_PUBLIC_API_BASE || "http://3.75.182.41:8000",
    opsKey: process.env.NEXT_PUBLIC_OPS_KEY || "",
    adminSecret: process.env.NEXT_PUBLIC_ADMIN_SECRET || "",
  },

  // ─── Supabase ──────────────────────────────────────────────────────────
  supabase: {
    url: process.env.NEXT_PUBLIC_SUPABASE_URL || "REPLACE_WITH_SUPABASE_URL",
    anonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "REPLACE_WITH_SUPABASE_ANON_KEY",
  },

  // ─── KPI Funnel ────────────────────────────────────────────────────────
  funnel: [
    { id: "page_view", label: "Landing Views" },
    { id: "signup", label: "Signups" },
    { id: "first_scan", label: "First Scan" },
    { id: "collection_created", label: "Collection Created" },
    { id: "item_added", label: "Items Added" },
    { id: "marketplace_click", label: "Marketplace Clicks" },
    { id: "affiliate_purchase", label: "Affiliate Purchases" },
    { id: "pro_upgrade", label: "Pro Upgrades" },
    { id: "premium_upgrade", label: "Premium Upgrades" },
  ],

  // ─── Content / UGC ────────────────────────────────────────────────────
  classification: {
    hitMinViews: 50000,
    hitMinRetention: 0.4,
    hitMinShares: 100,
    averageMinViews: 10000,
  },

  formats: ["unboxing", "collection-tour", "grading-guide", "market-analysis", "deal-hunt", "comparison", "haul", "top-10"],

  hookTypes: ["reveal", "question", "suspense", "list", "challenge", "reaction", "before-after", "hot-take"],

  conceptClusters: ["unboxing", "collection-showcase", "deal-hunting", "grading-guide", "market-analysis", "rare-finds", "price-predictions", "new-releases"],

  // ─── Pods (Category-Based) ─────────────────────────────────────────────
  pods: [
    { id: "pokemon", name: "Pokemon Pod", language: "EN", color: "#FFD700" },
    { id: "mtg", name: "MTG Pod", language: "EN", color: "#8B5CF6" },
    { id: "funko", name: "Funko Pod", language: "EN", color: "#EC4899" },
    { id: "warhammer", name: "Warhammer Pod", language: "EN", color: "#EF4444" },
    { id: "sneakers", name: "Sneakers Pod", language: "EN", color: "#3B82F6" },
    { id: "watches", name: "Watches Pod", language: "EN", color: "#14B8A6" },
    { id: "vinyl", name: "Vinyl Pod", language: "EN", color: "#F97316" },
    { id: "general", name: "General Pod", language: "EN", color: "#81D8D0" },
  ],

  // ─── Social Accounts ──────────────────────────────────────────────────
  accounts: [
    { handle: "@collectai.app", language: "EN" },
    { handle: "@collectai.pokemon", language: "EN" },
    { handle: "@collectai.mtg", language: "EN" },
    { handle: "@collectai.funko", language: "EN" },
    { handle: "@collectai.sneakers", language: "EN" },
  ],

  // ─── Pipeline Stages ───────────────────────────────────────────────────
  pipelineStages: [
    { id: "idea", label: "Idea", color: "bg-gray-100 text-gray-600" },
    { id: "scripted", label: "Scripted", color: "bg-blue-100 text-blue-700" },
    { id: "filming", label: "Filming", color: "bg-purple-100 text-purple-700" },
    { id: "editing", label: "Editing", color: "bg-amber-100 text-amber-700" },
    { id: "ready", label: "Ready", color: "bg-cyan-100 text-cyan-700" },
    { id: "posted", label: "Posted", color: "bg-emerald-100 text-emerald-700" },
    { id: "tracking", label: "Tracking", color: "bg-rose-100 text-rose-700" },
  ],

  // ─── Commission Defaults ───────────────────────────────────────────────
  defaultCommissionPct: 10,
  defaultCOGSCents: 0,

  // ─── Top Categories (54 in CollectAI) ─────────────────────────────────
  topCategories: [
    "pokemon_tcg", "mtg", "funko", "lego", "hot_toys",
    "watches", "sneakers", "vinyl", "warhammer", "kpop",
    "yugioh", "one_piece_tcg", "disney", "manga", "anime_figures",
  ],

  // ─── Sidebar Navigation ───────────────────────────────────────────────
  modules: {
    overview: true,
    kpiDashboard: true,
    ugcAnalytics: true,
    accounts: true,
    sparkAds: true,
    swipeFile: true,
    pipeline: true,
    pods: true,
    creators: true,
    briefGenerator: true,
    videoGenerator: true,
    commissions: true,
    weeklyReports: true,
    // CollectAI-specific modules
    mlModels: true,
    workerHealth: true,
    marketplaceHealth: true,
    demandSignals: true,
    userManager: true,
    sponsorAnalytics: true,
  },
};

export type AppConfig = typeof APP_CONFIG;
