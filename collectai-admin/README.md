# CollectAI Admin Dashboard

Internal admin dashboard for CollectAI — the collectibles tracking & valuation platform.

Built with **Next.js 16**, **React 19**, **Tailwind CSS 4**, **Recharts 3**, and **TypeScript 5**.

## Quick Start

```bash
npm install
npm run dev        # http://localhost:3000
```

Log in with the PIN in the server-only `ADMIN_PIN` (see Environment below). There is no
default PIN and no client-side PIN: the browser asks `GET /api/admin/session`, and
`POST /api/admin/login` sets an 8-hour httpOnly cookie (5 wrong PINs → 15-minute lock).

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

The browser never calls the backend. Every call goes to the same-origin proxy
`/api/admin/api/<path>` (`src/app/api/admin/api/[...path]/route.ts`), which checks the
admin cookie, allows only the paths below, and adds `X-Ops-Key` on the server.
Supabase reads go through `/api/admin/sb/...` the same way (table allowlist, service role).

| Endpoint | Dashboard Tab |
|----------|--------------|
| `GET /ops/dashboard/stats` | Overview |
| `GET /ops/dashboard/users` | Users |
| `GET /ops/dashboard/sponsor-analytics` | Sponsors |
| `GET /ops/dashboard/intel-summary` | Intelligence Data |
| `GET /admin/worker-health` | Worker Health, Overview |
| `GET /admin/demand-summary` | Demand Signals |
| `GET /admin/models`, `GET /admin/metrics` | ML Models (read-only) |
| `GET /admin/kpi-summary` | KPI Funnel |
| `GET /admin/spend-summary`, `POST /admin/spend-budget` · `spend-pause` · `spend-reset` | Spend Monitor |

Not on the server (checked against `scripts/api.lock.json`, 2026-09-27), so not called:
`/admin/train_now`, `/admin/activate_best`, `/admin/reload` (models retrain weekly in
`model_retrain_worker`), `/admin/intelligence-summary`, `/admin/error-rate`, `/admin/deploy-history`.

**No invented numbers.** A failed request shows its error; an empty result shows zeros
with the reason ("Showing zeros — no videos posted in the last 30 days"). Sample data only
with `NEXT_PUBLIC_ADMIN_DEMO=true`, under an amber "Demo Mode" banner. Until 2026-09-27
every failure silently rendered demo numbers (2,847 users against a real 10).

`npm run check:columns` — every column a Supabase query names must exist in
`../scripts/schema.lock.json`.

## Environment Variables

```env
# Public (inlined into the browser bundle — never put a secret here)
NEXT_PUBLIC_API_BASE=https://api.sparrowcollect.com   # read server-side by the proxy
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
# NEXT_PUBLIC_ADMIN_DEMO=true                          # opt-in sample data

# Server-only
ADMIN_PIN=...
ADMIN_SESSION_SECRET=...           # random string, signs the session cookie
SUPABASE_SERVICE_ROLE_KEY=...
OPS_API_KEY=...                    # same value as OPS_API_KEY on the API server
```

⛔ Never `NEXT_PUBLIC_OPS_KEY` / `NEXT_PUBLIC_ADMIN_PIN` / `NEXT_PUBLIC_ADMIN_SECRET`:
until 2026-09-27 those three shipped the ops key and the login PIN to every browser.

## Deploy

```bash
npm run build
npx vercel         # or deploy to any Node.js hosting
```

Recommended domain: `admin.collectai.app`
