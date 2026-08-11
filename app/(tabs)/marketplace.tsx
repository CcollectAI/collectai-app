/**
 * Market tab — opens directly onto the member marketplace grid.
 *
 * Until 2026-08-11 this tab was a discovery hub (search, collectors, open bids,
 * demand heat, movers) and the actual marketplace sat one tap deeper behind a
 * row on it. A tab named Market that opened a search page is the same
 * name-vs-destination mismatch that made the old "Search" tab open the
 * marketplace — fixed in the same spirit: one name, one destination.
 *
 * Renders the SAME implementation as `/listings` rather than a copy, so there
 * is one member marketplace, not two that drift. `asTab` suppresses the back
 * chevron and the in-body QuickNavBar, neither of which belongs on a tab.
 *
 * The hub was moved to `app/market-hub.tsx`, not deleted, and is reachable from
 * the control row on this screen.
 */
import MemberMarketplace from '../listings';

export default function MarketTab() {
  return <MemberMarketplace asTab />;
}
