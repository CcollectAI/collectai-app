#!/usr/bin/env bash
set -euo pipefail
ts="$(date -u +%Y%m%d-%H%M%S)"

echo "== 0) Snapshot current state =="
git add -A || true
git commit -m "[lock $ts] UI baseline accepted (icons via SVG, layout/theme stable)" || true
git tag -f "lock-ui-baseline-$ts" || true
mkdir -p backups
tar -czf "backups/collectai-lock-$ts.tar.gz" . \
  --exclude='./backups/*.tar.gz' \
  --exclude='./node_modules' \
  --exclude='./.expo' \
  --exclude='./.git' || true
echo "✔ Backup: backups/collectai-lock-$ts.tar.gz"
echo

echo "== 1) Write Roadmap Docs =="
mkdir -p docs/roadmap

# High-level roadmap overview
cat > docs/roadmap/README.md <<'MD'
# CollectAI — Build-Out Roadmap

This roadmap starts from the **locked UI baseline** (Tiffany blue + navy + white; square cards; Expo Router-only; SVG icons).  
We’ll keep UI polish iterative, while adding **capabilities** and **data plumbing**.

## Structure
- Sprint 1: Chart + Items + Add + Marketplace (foundations & UX depth)
- Sprint 2: Data persistence (Supabase) + Search aggregation + Share/Export
- Sprint 3: AI hooks (image → category/value) + Realtime (chat & price ticks)
- Ongoing: QA, performance, a11y, analytics, release hardening

Each task uses your preferred format: **Title + Files/Routes + Goal + Success criteria**.

MD

# Sprint 1 detail (screen-by-screen tasks)
cat > docs/roadmap/sprint-1.md <<'MD'
# Sprint 1 — UX Depth & Foundations

> Focus: elevate chart, tighten Items presentation, complete Add & Marketplace Sell flows (mock), keep navigation strict (Expo Router only).

---

## Portfolio — Chart polish & layout tighten
- **Files/Routes:** `app/(tabs)/index.tsx`, `src/components/LineChart.tsx`
- **Goal:** Professional line chart (no overshoot), right-aligned range toggle (1D/7D/30D), hi/low badges, tidy gridlines; tighten paddings and reduce whitespace.
- **Success criteria:**
  - Line never exceeds plot area; axes/padding consistent.
  - Range buttons aligned right; active state visible.
  - Hi/Low badges render with EUR values; tooltips on touch.
  - “Items” title in white box under chart; Watchlist section restored below items.

---

## Items — Spacing, shields, share & export
- **Files/Routes:** `app/(tabs)/items.tsx`, `src/components/ShieldBadge.tsx`, `src/export/**/*`
- **Goal:** Clean rows (name widest; % under name), colored shield per category (right-aligned), top-right Share action, centered “Download overview” at bottom, CSV export stub.
- **Success criteria:**
  - Category header: shield color reflects tier (silver/gold/platinum).
  - Pricing shows **no extra decimals** unless needed.
  - Share opens native share sheet; CSV export creates a file (mock ok).
  - Category “Total” sits below the card (not inside).

---

## Add — Camera-first + manual inputs (dropdowns)
- **Files/Routes:** `app/(tabs)/add.tsx`, `src/components/CompactSelect.tsx`, `src/lib/camera.ts`, `src/lib/predict.ts`
- **Goal:** Top “Use AI Prediction & Take a picture” card → camera/gallery; below that, manual entry with **scrollable dropdowns** (category, year, condition, brand/series) + notes; on save, item appears on Items screen.
- **Success criteria:**
  - Camera/gallery works (mock ok); fields prefill stubs based on category.
  - Dropdown popovers anchor under the trigger (popover-style).
  - Notes field present; saving adds to Items (local store mock ok).

---

## Marketplace — Search & Sell (vertical, tidy)
- **Files/Routes:** `app/(tabs)/marketplace.tsx`, `src/components/SearchRow.tsx`
- **Goal:** 
  - **Search:** one-box input + dropdown filters (category/type/sort/min/max) with normalized list results.
  - **Sell:** vertical form (Category/Method/Year/Condition + Title/Price/Notes) with mock Publish; fields aligned; dropdowns compact.
- **Success criteria:**
  - Search results list is vertically aligned, compact, with badge hints.
  - Sell form submits a payload (mock alert); guidance copy present.

---

## Navigation & Theme consistency
- **Files/Routes:** `app/(tabs)/_layout.tsx`, `app/_layout.tsx`, `src/theme.ts`
- **Goal:** Headers show crisp white line; titles: “Portfolio” (home), “Items”, “Add”, “Marketplace”; icons via **SVG** everywhere.
- **Success criteria:**
  - No “?” placeholders anywhere; icons render on all tabs and headers.
  - Header Settings on Portfolio; Share on Items.
  - Consistent paddings per theme scale.

MD

# Sprint 2 and 3 previews
cat > docs/roadmap/sprint-2-3.md <<'MD'
# Sprint 2 — Persistence, Exports, Aggregation

## Data persistence (Supabase)
- **Files:** `src/lib/db.ts`, `src/store/**/*`, `supabase/schema.sql`
- **Goal:** Persist Items, Watchlist, Listings, Chat messages. Keep **@** alias paths.
- **Success criteria:** CRUD works offline-first (fallback to local storage), syncs when online.

## Exports & Share
- **Files:** `src/export/csv.ts`, `src/export/pdf.ts` (optional)
- **Goal:** CSV export for Items and Portfolio; share via native sheet.
- **Success criteria:** Tap “Download overview” creates a CSV; “Share” attaches it.

## Search Aggregation (Mock → Pluggable)
- **Files:** `src/lib/search/*.ts`
- **Goal:** Adapter pattern that normalizes results from multiple sources.
- **Success criteria:** Toggle adapters; stable normalized row shape.

---

# Sprint 3 — AI & Realtime

## AI: Image → Category/Value (stub → model)
- **Files:** `src/lib/predict.ts`, `src/lib/models/value.ts`
- **Goal:** On Add photo, return category + price range (mock); later wire to model.
- **Success criteria:** Prefill forms with confidence; allow user override.

## Realtime chat + price ticks (mock → live)
- **Files:** `src/lib/live.ts`, `app/(tabs)/marketplace.tsx`
- **Goal:** Chat shows message streaming; “typing” indicator; price tickers.
- **Success criteria:** UI feels live; easy to swap in real backend.

MD

# Backlog in YAML (machine & human readable)
cat > docs/roadmap/backlog.yaml <<'YAML'
# CollectAI Backlog (prioritized)
- id: PORT-CHART-001
  area: Portfolio
  title: "Chart: right-aligned range, hi/low badges, no overshoot"
  files: ["app/(tabs)/index.tsx","src/components/LineChart.tsx"]
  goal: "Professional chart with tidy gridlines; range toggle on the right"
  criteria:
    - "Line never exceeds chart area"
    - "Hi/Low badges show EUR values"
    - "1D/7D/30D active state clear"
  effort: M

- id: ITEMS-EXPORT-002
  area: Items
  title: "CSV export + Share"
  files: ["app/(tabs)/items.tsx","src/export/csv.ts"]
  goal: "Export items to CSV and share via native sheet"
  criteria:
    - "Download overview creates CSV file"
    - "Share attaches CSV"
  effort: S

- id: ADD-CAMERA-003
  area: Add
  title: "Camera/gallery + prediction stub + manual dropdowns"
  files: ["app/(tabs)/add.tsx","src/lib/camera.ts","src/lib/predict.ts","src/components/CompactSelect.tsx"]
  goal: "Photo-first flow with prefill; manual inputs via compact dropdowns"
  criteria:
    - "Image capture works"
    - "Predicted category/price filled (mock ok)"
    - "Notes included; item appears on Items"
  effort: M

- id: MKT-SELL-004
  area: Marketplace
  title: "Sell form vertical layout (Category/Method/Year/Condition/Title/Price/Notes)"
  files: ["app/(tabs)/marketplace.tsx"]
  goal: "Tidy vertical Sell flow with Publish (mock)"
  criteria:
    - "All fields present; aligned"
    - "Publish shows payload alert"
  effort: S

- id: PERSIST-005
  area: Data
  title: "Supabase schema + local store sync"
  files: ["supabase/schema.sql","src/lib/db.ts","src/store/**/*"]
  goal: "Persist items/watchlist/listings/chat; offline-first"
  criteria:
    - "Create/Read/Update/Delete persisted"
    - "Works offline; syncs on reconnect"
  effort: L

- id: ANALYTICS-006
  area: Analytics
  title: "Event tracking stubs"
  files: ["src/lib/analytics.ts"]
  goal: "Track screen views, add item, export, chat send"
  criteria:
    - "Console logs in dev; pluggable providers"
  effort: S
YAML

echo "== 2) Add a tiny CLI to list tasks by area =="
mkdir -p scripts
cat > scripts/todo.sh <<'SH2'
#!/usr/bin/env bash
set -euo pipefail
area="${1:-all}"
file="docs/roadmap/backlog.yaml"
if [ ! -f "$file" ]; then echo "Backlog not found: $file"; exit 1; fi
if [ "$area" = "all" ]; then
  awk '/^- id:/{print ""; print $0} /^  area:/{print $0} /^  title:/{print $0}' "$file"
else
  awk -v a="$area" '
    $0 ~ /^- id:/ {blk=$0 RS; printflag=0}
    $0 ~ /^  area:/ {blk=blk $0 RS; if (tolower($2) ~ tolower(a)) printflag=1}
    $0 ~ /^  title:/ {blk=blk $0 RS; if (printflag) print blk}
  ' "$file"
fi
SH2
chmod +x scripts/todo.sh

echo
echo "== Done =="
echo "• Tag: lock-ui-baseline-$ts"
echo "• Roadmap: docs/roadmap/{README.md,sprint-1.md,sprint-2-3.md,backlog.yaml}"
echo "• List all tasks:  bash scripts/todo.sh"
echo "• List by area (e.g. Items):  bash scripts/todo.sh items"
