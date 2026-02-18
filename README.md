# CollectAI

Collectibles tracking, valuation, and smart deal discovery platform. Track your collection, get AI-powered price estimates, find deals across marketplaces, and never miss a collector event.

## Features

- **Smart Valuation** — Ridge regression ML models with q10/q50/q90 price bands and confidence scores
- **Barcode + Vision Scan** — Scan items via barcode or photo; 3-tier classification (CLIP, OpenAI, heuristic) across 36 categories
- **Marketplace Aggregation** — Search eBay, TCGPlayer, and Cardmarket with dedup and provenance scoring
- **Smart Deal Agent** — Set purchase mandates and get notified when matching deals appear
- **Price Monitoring** — Track price changes with threshold and anomaly alerts
- **Events** — Discover collector shows, conventions, and meetups
- **Dossier Export** — Generate item reports as JSON or HTML

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Mobile | React Native 0.81, Expo SDK 54, TypeScript |
| Backend | FastAPI, Python 3.12, Uvicorn |
| Database | Supabase (PostgreSQL), asyncpg |
| ML | scikit-learn Ridge regression, CLIP vision |
| Storage | AWS S3 (presigned URLs) |
| CI/CD | GitHub Actions, Docker |
| Hosting | AWS EC2 (eu-central-1) |

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
# Backend (1185+ tests)
cd server && python -m pytest tests/ --ignore=tests/test_inference.py -x -q

# Frontend
npx jest
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — System overview, agents, data flows
- [Deployment](docs/DEPLOYMENT.md) — Local dev, Docker, EC2, CI/CD
- [Taxonomy](docs/TAXONOMY.md) — 36-category classification system
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
