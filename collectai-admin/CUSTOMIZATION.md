# Customization Guide

Step-by-step instructions for setting up this admin dashboard for VascoApp or CollectAI.

---

## Step 1: Pick Your Preset

Open `admin.config.ts` and replace `APP_CONFIG` with one of the presets at the bottom of the file.

**For VascoApp:**
```ts
export const APP_CONFIG = {
  ...PRESETS.vascoApp,
  adminPin: "2026",
  supabase: {
    url: "REPLACE_WITH_SUPABASE_URL",
    anonKey: "REPLACE_WITH_SUPABASE_ANON_KEY",
  },
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
    commissions: true,
    weeklyReports: true,
  },
};
```

**For CollectAI:**
```ts
export const APP_CONFIG = {
  ...PRESETS.collectAI,
  adminPin: "2026",
  supabase: {
    url: "REPLACE_WITH_SUPABASE_URL",
    anonKey: "REPLACE_WITH_SUPABASE_ANON_KEY",
  },
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
    commissions: true,
    weeklyReports: true,
  },
};
```

---

## Step 2: Run the Supabase Migrations

Run all 5 SQL files in order in your Supabase SQL editor:

```
supabase/migrations/001_kpi_tables.sql         → creators, kpi_events, orders
supabase/migrations/002_shopify_enhanced_kpis.sql → daily_revenue, market_metrics
supabase/migrations/003_ugc_video_tracking.sql  → ugc_videos, ugc_daily_snapshots
supabase/migrations/004_content_pipeline_pods.sql → ugc_pods, ugc_pod_members, ugc_content_pipeline
supabase/migrations/005_swipefile_accounts_sparkads.sql → ugc_swipe_file, ugc_accounts, boost fields
```

These create the same schema for any app. The data you put in is what makes it app-specific.

---

## Step 3: Customize the Overview Tab

The Overview tab is a placeholder. Replace it with an app-specific component.

**For VascoApp — create `src/components/VascoOverview.tsx`:**
- Total contractors registered
- Active jobs this week
- Invoices sent / paid
- Revenue by market (NL, DE, FR, ES, IT, UK)
- Top trades (plumbing, electrical, painting, etc.)
- Onboarding completion rate

**For CollectAI — create `src/components/CollectAIOverview.tsx`:**
- Total users / collections
- Scans this week
- Marketplace clicks / affiliate revenue
- Top categories (Pokemon, MTG, Funko, etc.)
- Pro/Premium conversion rate
- Active sponsors

Then import and render in `AdminTabs.tsx`:
```tsx
{activeTab === "overview" && <VascoOverview />}
// or
{activeTab === "overview" && <CollectAIOverview />}
```

---

## Step 4: Customize the Funnel

The KPI Dashboard reads funnel stages from the `kpi_events` table. Your app needs to fire these events.

**VascoApp — add to your React Native app:**
```ts
// In your Supabase event tracking service:
trackEvent("signup");              // User creates account
trackEvent("onboarding_complete"); // Finishes onboarding wizard
trackEvent("first_job");           // Creates first job
trackEvent("first_quote");         // Sends first quote
trackEvent("first_invoice");       // Sends first invoice
trackEvent("invoice_paid");        // Invoice gets paid
trackEvent("subscription");        // Subscribes to paid plan
```

**CollectAI — add to your React Native app:**
```ts
trackEvent("signup");              // User creates account
trackEvent("first_scan");          // First item scanned
trackEvent("collection_created");  // First collection built
trackEvent("marketplace_click");   // Clicks marketplace link
trackEvent("affiliate_purchase");  // Purchase via affiliate
trackEvent("pro_upgrade");         // Upgrades to Pro
trackEvent("premium_upgrade");     // Upgrades to Premium
```

These events flow into `kpi_events` and the KPI Dashboard auto-computes the funnel.

---

## Step 5: Customize the Pods

Pods are organized differently per app:

**VascoApp pods = language markets:**
| Pod | Language | Focus |
|-----|----------|-------|
| NL Pod | Dutch | Dutch contractors, Dutch compliance |
| DE Pod | German | German market, DATEV integration |
| FR Pod | French | French market, Factur-X |
| ES Pod | Spanish | Spanish market, Facturae |
| IT Pod | Italian | Italian market, FatturaPA |
| UK Pod | English | UK market, Xero/QuickBooks |

**CollectAI pods = collector categories:**
| Pod | Focus | Content Style |
|-----|-------|--------------|
| Pokemon Pod | Pokemon TCG | Pack openings, grading, market analysis |
| MTG Pod | Magic: The Gathering | Deck showcases, rare finds, price spikes |
| Funko Pod | Funko Pops | Collection tours, exclusive hunts, display setups |
| Warhammer Pod | Warhammer | Build & paint, army showcases, tournament prep |
| General Pod | Cross-category | Collecting tips, market trends, deal hunting |

Seed these in Supabase via the `ugc_pods` table or use the demo data while developing.

---

## Step 6: Customize the Brief Generator

The Brief Generator auto-suggests hooks and formats from your analytics data. Customize:

1. **`admin.config.ts` → `formats`**: List the video formats your creators use
2. **`admin.config.ts` → `hookTypes`**: List the hook styles that work for your niche
3. **`admin.config.ts` → `conceptClusters`**: Group content themes

**VascoApp formats:** `["before-after", "tool-review", "day-in-life", "project-showcase", "tutorial", "testimonial"]`
**VascoApp hooks:** `["transformation", "problem-solution", "challenge", "behind-scenes", "tip", "myth-busting"]`
**VascoApp clusters:** `["contractor-life", "project-showcase", "before-after", "tool-tips", "business-growth", "compliance-tips"]`

**CollectAI formats:** `["unboxing", "collection-tour", "grading-guide", "market-analysis", "deal-hunt", "comparison"]`
**CollectAI hooks:** `["reveal", "question", "suspense", "list", "challenge", "reaction"]`
**CollectAI clusters:** `["unboxing", "collection-showcase", "deal-hunting", "grading-guide", "market-analysis", "rare-finds"]`

---

## Step 7: Connect Your Existing Analytics

**VascoApp** already has:
- `eventTrackingService.ts` — push events to Supabase. Map these to `kpi_events`.
- `analyticsService.ts` — business metrics. Surface these in the Overview tab.
- Existing Supabase tables — connect via the same project URL.

**CollectAI** already has:
- PostHog event tracking — keep for product analytics, mirror key events to `kpi_events` for the admin funnel.
- FastAPI backend at `/server/app/routes/admin_dashboard.py` — proxy health/stats data into the Overview tab.
- Stripe billing — surface subscription metrics in the Overview.
- Existing Supabase tables — connect via the same project URL.

---

## Step 8: Add App-Specific Setup Tabs

Replace the Settings placeholder in `AdminTabs.tsx` with your app's tools:

**VascoApp suggestions:**
- Compliance Dashboard (per-country e-invoicing status)
- Accounting Integration Manager (connect Moneybird, DATEV, etc.)
- Pricing Index Monitor (EU construction cost benchmarks)
- Contractor Onboarding Funnel

**CollectAI suggestions:**
- Category Manager (add/edit collector categories)
- Sponsor Campaign Manager (exists in-app, mirror to web admin)
- ML Model Monitor (scan accuracy, price prediction performance)
- Marketplace Integration Status (eBay, TCGPlayer API health)

---

## Step 9: Deploy

Both admin panels should be deployed as separate web apps:

```bash
# Install
npm install

# Development
npm run dev

# Build for production
npm run build

# Deploy to Vercel
npx vercel
```

**Recommended domains:**
- VascoApp: `admin.vasco.eu`
- CollectAI: `admin.collectai.app`

Set environment variables in Vercel:
```
NEXT_PUBLIC_ADMIN_PIN=your-pin
NEXT_PUBLIC_SUPABASE_URL=your-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-key
```

---

## Step 10: Ongoing Customization

As you use the dashboard, you'll want to:

1. **Replace demo data** — Connect Supabase and the demo data disappears automatically
2. **Add real creators** — Use the Creators tab to add your actual creator roster
3. **Seed pods** — Create pods in Supabase matching your market/category structure
4. **Build the swipe file** — Start saving competitor content that inspires your strategy
5. **Set up Shopify/Stripe webhook** — For automatic revenue attribution
6. **Integrate TikTok API** — For automatic video metrics pull (requires Business API access)
7. **Add WhatsApp Business API** — For automated pod notifications (requires Meta Business verification)

---

## File Reference

```
admin.config.ts              ← EDIT THIS FIRST (all settings)
src/app/admin/AdminShell.tsx  ← Auth gate + header (reads from config)
src/app/admin/AdminTabs.tsx   ← Sidebar nav + tab routing (add your tabs here)
src/components/Admin*.tsx     ← Dashboard components (work out of the box)
src/lib/kpi.ts                ← Types + queries + demo data
src/lib/pod-planner.ts        ← Pod + pipeline data
src/lib/briefs.ts             ← Brief generator logic
src/lib/commissions.ts        ← Commission calculator
src/lib/weekly-report.ts      ← Weekly report generator
src/lib/supabase.ts           ← Supabase client (reads from config)
supabase/migrations/          ← Run these in your Supabase project
```

---

## Quick Start Commands

```bash
# Clone and customize for VascoApp
cp -r ~/Downloads/admin-dashboard-template ~/Projects/vasco-admin
cd ~/Projects/vasco-admin
# Edit admin.config.ts with vascoApp preset
npm install && npm run dev

# Clone and customize for CollectAI
cp -r ~/Downloads/admin-dashboard-template ~/Projects/collectai-admin
cd ~/Projects/collectai-admin
# Edit admin.config.ts with collectAI preset
npm install && npm run dev
```
