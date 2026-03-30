# CollectAI Admin Dashboard

Internal admin dashboard for CollectAI — the collectibles tracking & valuation platform.

Built with **Next.js 16**, **React 19**, **Tailwind CSS 4**, **Recharts 3**, and **TypeScript 5**.

## Quick Start

```bash
npm install
npm run dev        # http://localhost:3000
```

Default PIN: `2026` (override with `NEXT_PUBLIC_ADMIN_PIN` env var).

## Features

- **Dark mode** — system preference detection + manual toggle (light/dark/system)
- **Responsive** — mobile hamburger sidebar, desktop collapsible sidebar
- **Auto-refresh** — configurable per-tab with LIVE/PAUSED indicator
- **Animated counters** — numbers tick up on load with ease-out timing
- **Skeleton loaders** — shimmer placeholders during data fetches
- **Toast notifications** — slide-in alerts for anomalies and actions
- **Recharts visualizations** — pie charts, bar charts, area charts, sparklines, heatmaps
- **Forecast lines** — moving average predictions on revenue/views charts
- **Cohort heatmaps** — creator performance over weeks
- **Posting time analysis** — best hour/day heatmap for content scheduling
- **Automation** — auto-brief generation, pipeline rules, digest scheduling

## Architecture (58 source files)

```
admin.config.ts                  <- All settings (branding, colors, funnel, pods, modules)
src/
  app/
    providers.tsx                <- ThemeProvider + ToastProvider
    admin/
      AdminShell.tsx             <- PIN gate + sticky header + ThemeToggle
      AdminTabs.tsx              <- Responsive sidebar + 22 tab routing
  components/
    CollectAIOverview.tsx        <- Overview with Recharts, auto-refresh, MetricCards
    AdminMLModels.tsx            <- ML model monitor (train, activate, MAE)
    AdminWorkerHealth.tsx        <- Worker health (auto-refresh 60s)
    AdminDemandSignals.tsx       <- Demand signals with Recharts bar chart
    AdminUserManager.tsx         <- Paginated user management
    AdminSponsorAnalytics.tsx    <- Sponsored events analytics
    IntelligenceTab.tsx          <- Forecast + cohort + posting time + sparklines
    AutoBriefScheduler.tsx       <- Auto-generate weekly briefs per pod
    PipelineAutomation.tsx       <- Pipeline auto-advance rules
    DigestScheduler.tsx          <- Scheduled digest exports
    Admin*.tsx                   <- Template components (KPI, UGC, pipeline, pods, etc.)
    ui/
      MetricCard.tsx             <- Pro-grade card with counter + trend + sparkline
      AnimatedCounter.tsx        <- requestAnimationFrame counter animation
      Skeleton.tsx               <- Shimmer loading placeholders
      Sparkline.tsx              <- Inline Recharts sparkline
      Toast.tsx                  <- Toast notification system
      ThemeToggle.tsx            <- Light/dark/system toggle
    charts/
      ForecastChart.tsx          <- Area chart with forecast dashed line
      CohortHeatmap.tsx          <- Creator performance heatmap
      PostingTimeHeatmap.tsx     <- 7x24 hour/day posting analysis
  hooks/
    useTheme.tsx                 <- Dark mode with localStorage + system preference
    useAutoRefresh.tsx           <- Configurable auto-refresh intervals
    useAnomalyDetection.tsx      <- Threshold-based metric anomaly alerts
  lib/
    collectai-api.ts             <- FastAPI backend client (9 endpoints)
    supabase.ts                  <- Supabase client (reads from config)
    kpi.ts, pod-planner.ts       <- KPI + Pod types + demo data
    briefs.ts, commissions.ts    <- Brief generator + commission calculator
    weekly-report.ts             <- Weekly report generator
    content-machine/
      types.ts                   <- All content machine type definitions
      seed-data.ts               <- Accounts, pillars, niches, products, mappings
      idea-generator.ts          <- 30-idea generator with hook templates + success fields
      calendar-generator.ts      <- Weekly calendar with pillar mix enforcement
      caption-generator.ts       <- 6-language caption packs (organic + commerce)
      batch-planner.ts           <- Batch filming planner with shot-by-shot checklists
      persistence.ts             <- Supabase + localStorage save/load/update
      index.ts                   <- Public API re-exports
```

## Navigation (23 Tabs)

**Platform:** Overview, Users, KPI Funnel, Sponsors, Developer Hub
**Intelligence:** ML Models, Worker Health, Demand Signals
**Content Marketing:** Content Machine, UGC Analytics, Social Accounts, Spark Ads, Swipe File, Pipeline, Category Pods, Creators, Brief Generator, Video Generator, Commissions, Weekly Reports
**Automation:** Intelligence, Auto Briefs, Pipeline Rules, Digest Scheduler

## Content Machine

One-click weekly content generation engine with 4 tabs:

- **Ideas** — 30 structured ideas with hooks (15+ templates/pillar), shot lists, voiceover scripts, success-pattern fields, TikTok SEO. Filter by pillar, account, status, or search. Status workflow (draft/approved/scheduled/filmed/posted/archived) and priority editing per idea. Visual pillar distribution bar.
- **Calendar** — Weekly calendar with pillar mix enforcement, account balance, batch film day. Distribution table with target vs actual. Responsive 2-col mobile / 7-col desktop grid. Markdown export.
- **Captions** — Full 6-language caption packs (all 9 pillars have dedicated templates, not generic fallback). Language switcher with ARIA tabs. 15 packs x 6 languages = 90 captions. Pillar-specific hashtag boosts.
- **Batch Plan** — Filming planner sorted by setup type. Pre/post checklists persisted to localStorage. Collapsible shot lists with `<details>`. Filmed count tracker.

Additional features:
- **Series generation** — Modal to create 5-part content series by pillar + niche
- **Persistence** — Auto-saves to localStorage (survives refresh). Supabase read/write when configured.
- **Accessibility** — ARIA roles (tab/tablist/tabpanel/aria-expanded), aria-labels, title tooltips, role=alert on warnings

### Content Machine Architecture

- **3 accounts**: @collectai.app (brand), @collectai.finds (deals/unboxing), @collectai.grail (grails/showcase)
- **9 pillars**: Market Alert (20%), Deal Hunting (15%), Collection Showcase (15%), Grading Guide (10%), Unboxing & Reveal (10%), Price Prediction (10%), Beginner Guide (10%), Collector Lifestyle (5%), App Feature (5%)
- **12 niches**: Pokemon TCG, MTG, Funko, LEGO, Sneakers, Watches, Vinyl, Warhammer, Yu-Gi-Oh!, K-pop, Hot Toys, Manga
- **7 products**: CollectAI Free/Pro, QuickScan, Portfolio Analytics, Deal Desk, Price Alerts, AI Condition Grading
- **Success fields**: objective_type, commerce_mode, presence_mode, paid_candidate, affiliate_ready, boostable_reason, target_completion_rate, target_save_rate
- **Hooks**: 15+ templates per pillar (140+ total), niche-aware price interpolation, 8-attempt deduplication
- **Captions**: All 9 pillars have dedicated templates in 6 languages (162 unique templates). Pillar-specific + niche-specific + localized hashtags
- **Persistence**: localStorage auto-save + Supabase upsert when configured
- **Database**: `006_content_machine.sql` (10 tables, 13 indexes, RLS), `007_content_machine_seeds.sql` (seed data)

## Backend API Endpoints

| Endpoint | Dashboard Tab |
|----------|--------------|
| `GET /ops/dashboard/stats` | Overview |
| `GET /ops/dashboard/users` | User Manager |
| `GET /ops/dashboard/sponsor-analytics` | Sponsor Analytics |
| `GET /admin/worker-health` | Worker Health |
| `GET /admin/demand-summary` | Demand Signals |
| `GET /admin/models` | ML Models |
| `GET /admin/metrics` | ML Models |
| `POST /admin/train_now` | ML Models (retrain) |
| `POST /admin/activate_best` | ML Models (activate) |
| `POST /admin/reload` | ML Models (reload cache) |

## Environment Variables

```env
NEXT_PUBLIC_ADMIN_PIN=2026
NEXT_PUBLIC_API_BASE=http://3.75.182.41:8000
NEXT_PUBLIC_OPS_KEY=your-ops-key
NEXT_PUBLIC_ADMIN_SECRET=your-admin-secret
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

## Deploy

```bash
npm run build
npx vercel         # or deploy to any Node.js hosting
```

Recommended domain: `admin.collectai.app`
