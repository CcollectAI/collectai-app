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
 * 2026-08-11: this is a REAL TAB again, restored to what it was built for — one
 * query across items, catalogue, collectors, events and categories. It stopped
 * being `href: null` when the fifth slot stopped calling itself Search while
 * opening the marketplace.
 *
 * It renders the same implementation as `/search` rather than a copy, so there
 * is ONE unified search, not two that drift. The single difference is
 * `asTab`, which suppresses the two affordances that only make sense on a
 * PUSHED screen: the in-body QuickNavBar (this route already has the tab bar —
 * rendering both stacks two, and the lower covers the last results) and the
 * back chevron (a tab has nothing to go back to, so `safeGoBack` would find an
 * empty stack and jump to Portfolio instead).
 *
 * `/search` stays a valid route and a valid deep link. The market search bar
 * keeps pushing THERE, not here: `npm run check:params` resolves a push target
 * to its route FILE, and this file has no `useLocalSearchParams` of its own — so
 * pushing here would report "that route reads: (none)" and the `?q=` contract
 * would stop being checkable.
 */
import SearchScreen from '../search';

export default function SearchTab() {
  return <SearchScreen asTab />;
}
