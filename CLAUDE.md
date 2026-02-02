# CollectAI - Project Memory

## Overview
CollectAI is a collector app for tracking collectibles (Pokemon, MTG, Funko, Warhammer, etc.) with AI-powered scanning and valuation.

## Tech Stack
- **Frontend:** Expo (React Native) with Expo Router
- **Backend:** FastAPI (Python) with Supabase/PostgreSQL
- **ML:** Ridge regression models for price prediction
- **Theme:** Tiffany Blue (#81D8D0) accent, EUR currency

## Key Files
- `app/(tabs)/_layout.tsx` - Main tab navigation (5 tabs: Portfolio, Items, Add, Events, Marketplace)
- `app/(tabs)/index.tsx` - Portfolio dashboard with line chart
- `app/(tabs)/items.tsx` - Item list with search/filter, multi-select, bulk operations
- `app/(tabs)/add.tsx` - QuickScan and manual add entry
- `app/quickscan.tsx` - Camera capture flow
- `app/item/[id].tsx` - Item detail with price bands
- `app/analytics.tsx` - Portfolio insights dashboard
- `src/data/DataProvider.ts` - Data interface
- `src/data/MockDataProvider.ts` - Mock implementation
- `src/taxonomy/` - Category classification system

## Data Flow
```
UI Components → dataProvider (singleton)
  ├─ MockDataProvider (default, for development)
  └─ SupabaseDataProvider (mode="real", for production)
```

---

## UI/UX Improvement Roadmap

### Priority 1: Core Flow Friction Reducers

#### 1.1 "I Got It!" Wishlist → Portfolio Flow ✅ DONE
- [x] Add "Mark as Acquired" button on wishlist item detail
- [x] One-tap creates item in portfolio with pre-filled data
- [x] "Congrats!" animation on acquisition
- [x] Prompt for actual purchase price (feeds ML model)
- **Files:** `app/(tabs)/wishlist.tsx`, `src/data/DataProvider.ts`

#### 1.2 QuickScan Result Enhancement ✅ DONE
- [x] Price confidence gauge/meter visualization
- [x] "Why this price?" expandable explanation section
- [x] Quick-edit inline for name/category before saving
- [x] "Scan Another" button for batch sessions
- **Files:** `app/item/[id].tsx`, `src/components/PriceConfidenceGauge.tsx`

#### 1.3 Category Drill-Down from Item Detail ✅ DONE
- [x] Tappable category pill → category store
- [x] "See X similar items" link
- [x] "Missing from this set" teaser
- **Files:** `app/item/[id].tsx`, `app/categories/[categoryId].tsx`

### Priority 2: Engagement & Delight

#### 2.1 Portfolio Milestones & Achievements ✅ DONE
- [x] Achievement badges: "First item", "10 items", "€1000 portfolio"
- [x] Streak tracking for daily activity
- [x] Tier system (bronze, silver, gold, platinum)
- **Files:** `src/lib/achievements.ts`, `src/components/AchievementBadge.tsx`

#### 2.2 Visual Collection Grid (Gallery View) ✅ DONE
- [x] Toggle between list/grid on Items tab
- [x] Pinterest-style image grid
- [x] Tap to zoom with lightbox modal
- **Files:** `app/(tabs)/items.tsx`, `src/components/ItemGalleryGrid.tsx`

#### 2.3 Price Alert Animations ✅ DONE
- [x] Pulse animation on significant value change
- [x] Red/green micro-animation on price delta
- [x] "Hot" badge on trending items
- **Files:** `src/components/PriceDeltaBadge.tsx`

### Priority 3: Discovery & Social

#### 3.1 "Collectors Like You" Recommendations
- [ ] "People who collect X also collect Y" on category store
- [ ] Surface overlapping collections from public profiles
- [ ] "Follow Collection" feature
- **Files:** `app/categories/[categoryId].tsx`, `src/data/DataProvider.ts`

#### 3.2 Event Integration Improvements ✅ DONE
- [x] Native calendar integration (iOS/Android)
- [x] Countdown timers for upcoming drops
- [x] "Set Reminder" with push notification
- [x] Separate upcoming/past events sections
- **Files:** `app/(tabs)/events.tsx`, `src/lib/calendar.ts`, `src/components/EventCountdown.tsx`

#### 3.3 Marketplace Trust Integration
- [ ] "For Sale" listings on item detail
- [ ] Trust score badge on sellers
- [ ] "Price Check" comparing value to market
- **Files:** `app/item/[id].tsx`, `src/components/MarketListings.tsx` (new)

### Priority 4: Power User Features

#### 4.1 Bulk Operations ✅ DONE
- [x] Multi-select mode on Items tab
- [x] Bulk category reassignment
- [x] Bulk export selected items
- [x] Bulk delete with confirmation
- [x] Long-press to enter multi-select
- **Files:** `app/(tabs)/items.tsx`, `src/hooks/useMultiSelect.ts`

#### 4.2 Advanced Filters & Sorting ✅ DONE
- [x] Filter by: condition, price range, category
- [x] Sort by: value (high/low), name (A-Z/Z-A), recently added
- [x] Save filter presets with names
- [x] Collapsible filter sections
- **Files:** `app/(tabs)/items.tsx`, `src/components/FilterSheet.tsx`

#### 4.3 Portfolio Insights Dashboard ✅ DONE
- [x] Category breakdown pie chart
- [x] Best/worst performers
- [x] Liquidity score
- [x] Diversity index
- [x] Portfolio tier badges
- **Files:** `app/analytics.tsx`, `src/components/PortfolioPieChart.tsx`

### Quick Wins ✅ ALL DONE

| Feature | Status | File |
|---------|--------|------|
| Haptic feedback on save/delete | [x] | `src/lib/haptics.ts` |
| Pull-to-refresh on all lists | [x] | Items, Events, Wishlist |
| Empty state illustrations | [x] | `src/components/EmptyState.tsx` |
| Skeleton loaders | [x] | `src/components/Skeleton.tsx` |
| Swipe-to-delete | [x] | `src/components/SwipeableRow.tsx` |
| Long-press context menu | [x] | Multi-select mode on Items |

---

## Implementation Notes

### Completed UI/UX Sprint (2026-02-02)
- [x] Full UI/UX improvement roadmap implemented
- [x] 12 major features completed
- [x] 6 quick wins implemented
- [x] All core components created and integrated

### New Components Created
- `src/components/PriceConfidenceGauge.tsx` - Visual confidence meter
- `src/components/PriceDeltaBadge.tsx` - Price change animations
- `src/components/ItemGalleryGrid.tsx` - Pinterest-style grid
- `src/components/AchievementBadge.tsx` - Achievement display
- `src/components/EventCountdown.tsx` - Countdown timer
- `src/components/FilterSheet.tsx` - Advanced filter modal
- `src/components/EmptyState.tsx` - Empty state illustrations
- `src/components/Skeleton.tsx` - Loading skeletons
- `src/components/SwipeableRow.tsx` - Swipe gestures
- `src/components/PortfolioPieChart.tsx` - Category breakdown

### New Utilities Created
- `src/lib/haptics.ts` - Tactile feedback
- `src/lib/calendar.ts` - Calendar/notification integration
- `src/lib/achievements.ts` - Achievement system
- `src/hooks/useMultiSelect.ts` - Multi-selection hook

### Completed Cleanup (2026-02-02)
- [x] ErrorBoundary integrated into root layout
- [x] Comprehensive .env.example documentation
- [x] .gitignore updated for backup files
- [x] Logger utility created (src/lib/logger.ts)
- [x] Console.log replaced with logger in critical paths

### Taxonomy System
- Version: 2026.02.02
- Categories: Pokemon, MTG, Yugioh, Funko, Lorcana (Phase 1) + more
- Collection tags: BTS, Taylor Swift, Disney, Star Wars, etc.
- Deterministic mapper with confidence scores

### Environment Variables
See `.env.example` for full documentation. Key vars:
- `EXPO_PUBLIC_SUPABASE_MODE` - "mock" or "real"
- `API_SHARED_SECRET` - Backend API authentication
- `DB_ENABLED` - Database connectivity toggle
