# Sparrow Collect

Collectibles tracking, valuation, and smart deal discovery platform. Track your collection, get AI-powered price estimates, find deals across 44 marketplaces, and never miss a collector event.

Renamed from CollectAI 2026-05-04. Domain: [sparrowcollect.com](https://sparrowcollect.com). Bundle ID: `io.sparrowcollect.app`. Currently building TestFlight build #13 (2026-05-19).

## Features

- **Smart Valuation** — 36 Ridge regression models with q10/q50/q90 price bands, confidence scores, partition-pruned price history (~99K predictions, 528K market hits)
- **Barcode + Vision Scan** — Scan via barcode or photo; 3-tier classification (CLIP, OpenAI, heuristic) across **54 categories** with ~140K curated catalog items
- **Marketplace Aggregation** — 44 adapters covering eBay (Browse), Mercari, Vinted, TCGPlayer (where accessible), Discogs, Catawiki, regional classifieds (Leboncoin, Marktplaats, Kleinanzeigen, Wallapop, Gumtree, Depop, 130point) + 30+ category specialists. Dedup + FX-normalised EUR + provenance scoring.
- **Smart Deal Hub** — Set purchase mandates, get notified when matching deals appear; ranked by deal score with pagination
- **Price Monitoring** — Threshold + anomaly alerts on tracked items, calibrated quantile bands
- **Events** — Discover collector shows, conventions, and meetups (Ticketmaster + SeatGeek + manual sources)
- **Inventory Export** — 12-col round-trip CSV + 30-col comprehensive snapshot (currency-aware via fx_service)
- **Onboarding** — Followed categories drive add-flow sort, scan classifier priors, AI catalog-match tiebreaker, home empty state, Deal Hub filter (2026-05-18)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Mobile | React Native 0.81, Expo SDK 54, TypeScript, Expo Router |
| Backend | FastAPI, Python 3.12, Uvicorn, asyncpg |
| Database | Supabase (PostgreSQL, eu-central-1), partitioned monthly |
| ML | scikit-learn Ridge regression (36 active models), CLIP vision, OpenAI fallback |
| Storage | AWS S3 (presigned URLs) + data lake (`collectai-warehouse-prod-eu-north-1`, lifecycle: 180d→Glacier IR→730d→Deep Archive) |
| Payments | RevenueCat (iOS IAP, shipped 2026-05-09); Stripe dormant for future web/Android |
| Monitoring | Sentry (backend + mobile), PostHog (31+ events), Telegram alerts (spend, circuit breakers, ingest stall) |
| CI/CD | GitHub Actions (ci-min, Sanity, Sanity E2E, Nightly Training, Nightly Eval), EAS Build |
| Hosting | AWS EC2 t3.medium (eu-north-1, Elastic IP `51.21.210.195`), systemd-supervised bake |

## Quick Start

### Backend

```bash
pip install -r requirements.txt
cd server
DEV_MODE=true DB_ENABLED=false uvicorn main:app --reload --port 8000
```

### Frontend

```bash
npm install
npx expo start
```

### Tests

```bash
# Backend (3,325 tests as of 2026-05-19)
cd server && python -m pytest tests/ --ignore=tests/test_inference.py -x -q

# Frontend (516 tests, 50 suites, 58 snapshots)
npx jest
```

## Documentation

- [Public Launch Checklist](docs/PUBLIC_LAUNCH_CHECKLIST.md) — **Active launch path: TestFlight → App Store with RevenueCat IAP**
- [Go-Live Checklist](GO_LIVE_CHECKLIST.md) — Infra setup (DNS, EC2, .env, EAS); mostly done
- [Architecture](docs/ARCHITECTURE.md) — System overview, agents, data flows
- [Deployment](docs/DEPLOYMENT.md) — Local dev, Docker, EC2, CI/CD
- [Runbook](docs/RUNBOOK.md) — Incident response triage tree
- [Monetization](docs/MONETIZATION.md) — RevenueCat IAP setup
- [TestFlight QA Checklist](docs/TESTFLIGHT_QA_CHECKLIST.md) — Run for each new build
- [App Store ASO](docs/app-store-aso.md) — Paste-ready ASC metadata
- [Data Scaling Plan](docs/DATA_SCALING_PLAN.md) — 12-month roadmap
- [Schema Lock](docs/schema-lock.md) — Per-table FE/BE read/write surface
- [Taxonomy](docs/TAXONOMY.md) — Category classification system (54 categories)
- [Market Data](docs/MARKET_DATA.md) — Marketplace integration details
- [Haptics](docs/haptics.md) — Haptic feedback patterns
- [Accessibility](docs/accessibility.md) — A11y guidelines
- [UI Playbook](docs/ui-playbook.md) — Component patterns

## Project Structure

```
app/                    # Mobile screens (file-based routing)
src/                    # Shared frontend code (components, hooks, API client)
server/
  app/                  # FastAPI application
    routes/             # API routers
    agents/             # Business logic agents
    ml/                 # ML model loading and inference
  workers/              # Background workers
  tests/                # Backend test suite
  pipelines/            # Data ingestion and training
docs/                   # Documentation
supabase/migrations/    # Database migrations
```

## License

Proprietary. All rights reserved.
