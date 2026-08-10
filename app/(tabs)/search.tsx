/**
 * Search tab → the global unified search screen.
 *
 * This route used to be `<Redirect href="/(tabs)/marketplace" />`, which is why
 * searching for something in the catalogue found nothing (2026-08-10).
 *
 * The chain was: the redirect sent every search to the marketplace screen, whose
 * `executeSearch` queries the user's OWN items, local category names, and an
 * external adapter search that is disabled pre-launch — it never touches
 * `category_items`. Meanwhile `app/search.tsx` — a complete unified search over
 * items, catalogue, collectors, events and categories, backed by
 * `GET /search/unified` and its trigram index — was reachable from nowhere: a
 * repo-wide grep for a push to `/search` returned zero hits.
 *
 * So "rolex daytona" returned nothing while `/catalog/watches/items?q=daytona`
 * returned 12 rows and the catalogue held 77 Rolexes. Nothing was missing from
 * the data; the screen that could find it was simply unwired.
 *
 * Re-exported rather than moved: `/search` stays a valid deep link, and both
 * routes render the same component, so there is ONE implementation of unified
 * search rather than two that can drift.
 *
 * The tab itself stays `href: null` in `(tabs)/_layout.tsx` — it is not a
 * sixth tab. It is reached by submitting the marketplace search bar, which
 * forwards the typed query as `?q=`.
 */
export { default } from '../search';
