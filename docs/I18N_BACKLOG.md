# i18n backlog — English rendered from code

> Generated 2026-09-24 by `node scripts/check-i18n-strings.mjs --all` (regenerate with that command; this file is a snapshot).
> **Not being worked on** — Merle, 2026-09-24: translation is not the priority. This is the list, ranked.

## Why the old number was wrong

The record said "no live English left" (66 deliberate). The lint only read JSX text and five props. On 2026-09-24 it was taught four more shapes — toast `message:`, `Alert.alert(...)` arguments and button labels (multi-line), `set*Error('…')`, and `userErrorMessage(err, '…')` fallbacks — and the count became **443**.

| shape | count |
|---|---|
| alert | 147 |
| toast-message | 135 |
| error-fallback | 62 |
| jsx-text | 54 |
| set-error | 33 |
| prop | 12 |

**38** of them already have a translation in the locale files and need only `t('<key>')` (run with `--wiring`).

## Done already (money screens, 2026-09-24)

- `app/subscription.tsx` — whole paywall: title, plan names, feature lists, buttons, store error, legal text, purchase/restore toasts.
- `app/(tabs)/wishlist.tsx` — Target Hit add/edit/remove toasts and dialog; watch toasts in `FavoriteWatchButtons`, `barcode-scan`, `catalog-item` (add path only).

## Remaining, by file (money-adjacent first)

| file | strings | area |
|---|---|---|
| `app/sell/dashboard.tsx` | 28 | money |
| `app/offers.tsx` | 22 | money |
| `app/listing/[id].tsx` | 7 | money |
| `app/purchase/create-mandate.tsx` | 7 | money |
| `app/listings.tsx` | 5 | money |
| `app/purchase/deal/[dealId].tsx` | 5 | money |
| `app/sell/ebay-defaults.tsx` | 5 | money |
| `app/purchase/index.tsx` | 4 | money |
| `app/sell/new.tsx` | 2 | money |
| `app/catalog-item/[key].tsx` | 1 | money |
| `app/sets-to-complete.tsx` | 1 | money |
| `app/(tabs)/items.tsx` | 28 | other |
| `src/components/settings/DevSentryCrashSection.tsx` | 20 | other |
| `src/components/settings/ProfileEditSection.tsx` | 19 | other |
| `app/quickscan.tsx` | 16 | other |
| `app/twitch-leaderboard.tsx` | 16 | other |
| `src/hooks/useItemDetail.ts` | 13 | other |
| `src/lib/calendar.ts` | 12 | other |
| `app/events/[eventId].tsx` | 11 | other |
| `app/inbox.tsx` | 11 | other |
| `app/projects/[id].tsx` | 11 | other |
| `app/add-manual.tsx` | 10 | other |
| `app/edit-event.tsx` | 10 | other |
| `app/mfa-setup.tsx` | 10 | other |
| `app/users/[userId].tsx` | 9 | other |
| `src/components/item/ItemCatalogRefresh.tsx` | 9 | other |
| `app/sponsor/dashboard.tsx` | 7 | other |
| `app/twitch.tsx` | 7 | other |
| `src/hooks/usePhotoUpload.ts` | 7 | other |
| `app/barcode-scan.tsx` | 6 | other |
| `src/components/SearchStatusPanel.tsx` | 6 | other |
| `src/components/settings/MarketplaceConnectionsSection.tsx` | 6 | other |
| `app/item/[id].tsx` | 5 | other |
| `app/offer/[offerId].tsx` | 5 | other |
| `app/settings/blocked-users.tsx` | 5 | other |
| `src/components/ItemsStatusPanel.tsx` | 5 | other |
| `app/(auth)/reset-password.tsx` | 4 | other |
| `app/(tabs)/add.tsx` | 4 | other |
| `src/components/DossierReportSection.tsx` | 4 | other |
| `src/components/ItemGallerySection.tsx` | 4 | other |
| `src/components/quickscan/ScanFeedbackPanel.tsx` | 4 | other |
| `src/components/settings/DevForcePlanSection.tsx` | 4 | other |
| `src/export/csv.ts` | 4 | other |
| `src/hooks/useItemGallery.ts` | 4 | other |
| `src/hooks/useItemGrading.ts` | 4 | other |
| `app/(tabs)/events.tsx` | 3 | other |
| `app/(tabs)/index.tsx` | 3 | other |
| `app/archived.tsx` | 3 | other |
| `src/components/share/ShareToChatSheet.tsx` | 3 | other |
| `app/(auth)/login.tsx` | 2 | other |
| `app/events/compose-announcement.tsx` | 2 | other |
| `app/import-url.tsx` | 2 | other |
| `app/leaderboard.tsx` | 2 | other |
| `src/app/+not-found.tsx` | 2 | other |
| `src/components/PortfolioChart.tsx` | 2 | other |
| `src/components/PriceTrendChart.tsx` | 2 | other |
| `src/components/p2p/SettleUpSheet.tsx` | 2 | other |
| `src/components/settings/PaymentHandlesSection.tsx` | 2 | other |
| `src/hooks/useAuth.ts` | 2 | other |
| `src/hooks/useEventForm.ts` | 2 | other |
| `src/hooks/useListForSale.ts` | 2 | other |
| `app/build-paint-projects.tsx` | 1 | other |
| `app/categories/[categoryId].tsx` | 1 | other |
| `app/chat/new.tsx` | 1 | other |
| `app/chat-demo.tsx` | 1 | other |
| `app/create-event.tsx` | 1 | other |
| `app/franchise/[id].tsx` | 1 | other |
| `app/sponsor/register.tsx` | 1 | other |
| `src/components/CatalogSuggestionModal.tsx` | 1 | other |
| `src/components/SplashScreen.tsx` | 1 | other |
| `src/components/TrendingCategoriesGrid.tsx` | 1 | other |
| `src/components/category/SetProgressSection.tsx` | 1 | other |
| `src/components/events/EventActionBar.tsx` | 1 | other |
| `src/components/home/DemandHeatSection.tsx` | 1 | other |
| `src/components/settings/NotificationPreferencesSection.tsx` | 1 | other |
| `src/hooks/useActionSheetPicker.ts` | 1 | other |
| `src/hooks/useAutoSetProgress.ts` | 1 | other |
| `src/hooks/useItemProgress.ts` | 1 | other |
| `src/lib/logger.ts` | 1 | other |
| `src/lib/purchases.ts` | 1 | other |
| `src/lib/supabase.ts` | 1 | other |

Not every finding needs translating: DEV-only screens (`DevSentryCrashSection`, `chat-demo`), and some strings belong to dead code that should be deleted instead — check before translating (see project_2026_09_19_a11y_i18n_slice).
