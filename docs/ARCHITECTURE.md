# Architecture

## System Overview

Sparrow Collect is a collectibles tracking and valuation platform with a React Native mobile app backed by a FastAPI server and Supabase/PostgreSQL database.

```
Mobile App (Expo/React Native)
       │
       ▼
   FastAPI Server (EC2 :8080)
       │
       ├── Supabase / PostgreSQL (data + auth)
       ├── S3 (image storage)
       ├── External APIs (eBay, TCGPlayer, Cardmarket)
       └── Background Workers (price monitor, deal discovery)
```

## Frontend

- **Framework**: Expo SDK 54 + React Native 0.81
- **Routing**: expo-router (file-based)
- **State**: React hooks + AsyncStorage for offline cache
- **API Client**: `src/api/collectorsApi.ts` — typed fetch wrapper
- **Theme**: Tiffany Blue (#81D8D0), dark mode support via `useAppTheme()`
- **Key Libraries**: expo-camera (barcode), expo-haptics, expo-image, FlashList, react-native-reanimated

### Directory Structure

```
app/                    # Screens (file-based routing)
  (tabs)/               # Tab navigator (home, search, scan, events, profile)
  purchase/             # Smart Deal Agent screens
  projects/[id].tsx     # Build & Paint project detail (category-aware)
  build-paint-projects  # Build & Paint project list + create
  categories/           # Category store screens
  analytics.tsx         # Portfolio analytics
  barcode-scan.tsx      # Camera scanner
src/
  api/                  # API client
  components/           # Reusable UI (Skeleton, Toast, LoadingButton, OfflineBanner)
  constants/            # buildStepTemplates.ts, categoryFields.ts
  data/                 # SupabaseDataProvider, types, categories (CATEGORY_VISUAL)
  hooks/                # useFormField, useEnterReveal, useNetworkStatus
  lib/                  # validate.ts, marketProviders/
  theme/                # colors, useAppTheme
types/                  # category.ts (36 categories)
```

## Backend

- **Framework**: FastAPI on Uvicorn
- **Database**: asyncpg direct connections to Supabase PostgreSQL
- **Auth**: JWT (Supabase-issued) + DEV_MODE bypass for local development
- **Workers**: Standalone Python processes for async tasks

### 6 Agentic Layers

| Agent | Purpose | Key File |
|-------|---------|----------|
| Pricing | Ridge regression v2, q10/q50/q90 quantile predictions | `app/ml/model_loader.py` |
| Alert & Insight | Threshold, anomaly, set completion alerts | `app/agents/alert_agent.py` |
| Learning & Calibration | Feedback loop, calibration gate | `app/agents/calibration_agent.py` |
| Vision & Classification | 3-tier: CLIP → OpenAI → heuristic (36 categories) | `app/ml/vision_classifier.py` |
| Marketplace Aggregation | Multi-source search, dedup, provenance scoring | `app/agents/marketplace_agent.py` |
| Smart Deal | Purchase mandates, policy engine, deal discovery | `app/agents/deal_discovery_agent.py` |
| Catalog Learning | Capture unrecognized items, auto-map by consensus, surface new category candidates | `features/catalog_learning_router.py` |

### Server Directory Structure

```
server/
  main.py               # FastAPI app, lifespan, router registration
  app/
    auth.py              # JWT validation, DEV_MODE, API key guards
    config.py            # Environment config with validation
    db.py                # asyncpg pool management
    db_helpers.py        # User-scoped query wrappers (RLS supplement)
    errors.py            # Standardized error_response()
    models/              # Pydantic response models
    routes/              # API routers (items, portfolio, pipeline, settings, etc.)
    features/            # Feature routers (events, quickscan, taxonomy)
    agents/              # Business logic agents (marketplace, deal, dossier)
    ml/                  # ML model loading, inference, vision
    lib/                 # Utilities (affiliate, s3_client, notify)
  workers/               # Background workers (17 registered)
    watchlist_monitor_worker.py   # Watchlist price monitoring (priority tiers: 15min/1hr/6hr)
    price_monitor_worker.py       # Threshold, anomaly, set completion alerts
    deal_discovery_worker.py      # Purchase mandate scanning + deal alerts
    auction_alert_worker.py       # Auction end-time alerts (5min cycle, eBay/Yahoo/Catawiki)
    value_change_worker.py        # Portfolio value change notifications
    insights_digest_worker.py     # Weekly collection digest
    catalog_learning_worker.py    # Auto-map + candidate pipeline
    vision_ingest_worker.py       # Vision classification queue
    alerts_worker.py              # Low-value item alerts
    event_scraper_scheduler.py    # Event ingestion (6hr cycle: crawl 41 targets + dedup + enrich)
    retry.py                      # Retry + dead letter infrastructure
  pipelines/             # Data ingestion and training pipelines
  tests/                 # pytest test suite (1486+ tests)
```

## Database Schema

Key tables in Supabase PostgreSQL:

| Table | Purpose |
|-------|---------|
| `items` | User collection items |
| `category_items` | Marketplace reference data per category |
| `model_registry` | ML model versions and metrics |
| `market_hits` | Price observations from marketplaces |
| `events` | Collector events (shows, conventions) |
| `event_attendees` | Event RSVPs |
| `user_category_follows` | Category notification preferences |
| `purchase_mandates` | Smart Deal Agent buy orders |
| `mandate_deals` | Matched deals for mandates |
| `user_settings` | Per-user preferences (currency, region, locale) |
| `catalog_suggestions` | User-submitted unrecognized item signals |
| `category_candidates` | Aggregated new category proposals |
| `event_templates` | Reusable event templates (save-as-template / create-from-template) |
| `sponsor_companies` | Sponsor company registrations + Stripe checkout |
| `event_announcements` | One-way broadcast messages from event hosts to attendees |
| `event_announcement_reads` | Read receipts for announcements (auto-mark-read) |
| `build_paint_projects` | Build & paint project tracking (category-specific status pipelines) |
| `build_step_templates` | Category-specific build workflow step templates |
| `notification_history` | Push notification log with read/unread tracking |
| `user_push_tokens` | Expo push notification tokens per device |
| `taxonomy_registry` | Category taxonomy versions |
| `object_pointers` | S3 image references |

## Data Flow

### Item Intake
```
Barcode Scan → Intake Agent → Taxonomy Resolver → Vision Classifier → Pricing Agent → DB
```

### Price Monitoring
```
Scheduler → Price Monitor Worker → Marketplace Agent → Price Update → Alert Agent → Push Notification
```

### Deal Discovery
```
Scheduler → Deal Discovery Worker → Marketplace Agent → Policy Engine → Score Deals → Notify User
```

### Notification System
```
Alert Fired (any worker) → app/lib/notify.py
  ├── Check user preference (notification_preferences JSONB)
  ├── Check frequency cap (5/day free, 15/day pro, 30/day premium)
  ├── Send via Expo Push API (all active tokens)
  └── Persist to notification_history
```

All workers route through the shared `notify_user()` helper which handles:
- **Preference-aware routing**: checks user's notification_preferences before sending
- **Frequency capping**: tier-based daily limits to prevent notification fatigue
- **Graceful fallback**: never crashes the worker if push fails

### Event Ingestion Pipeline
```
event_scraper_scheduler.py (every 6 hours, fully automated)
├── Firecrawl crawler (41 web targets: brands, conventions, retailers)
├── Crawl4AI crawler (same 41 targets, JS rendering for dynamic sites)
├── Newsletter scraper (35+ email-to-category mappings, if IMAP configured)
├── Cross-source deduplication (title similarity + date matching)
└── Enrichment (franchise tagging via 13 keyword patterns + Nominatim geocoding)
```

**41 web targets** covering: Pokemon, MTG, Warhammer, LEGO, Funko, Good Smile, K-pop, Taylor Swift, SDCC, NYCC, PAX, Gen Con, MCM, Essen Spiel, Anime Expo, Comiket, AnimeJapan, Sideshow, Hot Toys, Hasbro Pulse, Bandai, Topps, Pokemon Center, TCGPlayer, StockX, Sneaker News, Discogs, Record Store Day, Hodinkee, Watches & Wonders, Disney Parks, Fragrantica, Penworld, Catawiki, Eventbrite (5 search verticals)

### Build & Paint Status Pipelines

Category-specific status pipelines replace the coarse Active/Backlog/Completed system:

| Category | Pipeline |
|----------|----------|
| Warhammer | Wishlist → Purchased → Unassembled → Assembled → Primed → Battle Ready → Parade Ready → Finished |
| Scale Models | Wishlist → Purchased → Unassembled → Assembled → Primed → Painted → Weathered → Decaled → Finished |
| Gunpla | Wishlist → Purchased → On Sprue → Snap Built → Primed → Painted → Decaled → Top Coated → Finished |
| LEGO | Wishlist → Purchased → Sealed → Building → Built → Modified/MOC → Displayed |
| Keycaps | Wishlist → Parts Ordered → Parts Received → Lubing & Modding → Assembled → Tuned → Finished |

Endpoints: `GET /build-paint/status-pipelines` and `GET /build-paint/status-pipelines/{category_id}`

### Catalog Learning
```
Intake Miss (barcode/photo/url/manual) → catalog_suggestions → Worker (30min cycle)
  ├── 3+ users agree on name + existing category → Auto-map to category_items
  ├── Free-text category, 10+ signals → Track in category_candidates (watching)
  └── 25+ unique users in 30 days → Promote to candidate → Admin review
```

## Security

- JWT validation with issuer + audience + expiry checks
- User-scoped database queries via `db_helpers.py`
- SQL injection prevention via identifier whitelists
- Non-root Docker container
- Hostname-based DEV_MODE guard (localhost/127.* only)
