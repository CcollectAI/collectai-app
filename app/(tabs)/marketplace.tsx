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
 * The hub was parked at `app/market-hub.tsx` for a day and DELETED 2026-08-12
 * once its last three modules were resolved: Market Movers and Regional
 * insights moved onto this screen, and demand heat deliberately did not —
 * `app/analytics.tsx` already renders it behind `advanced_analytics`, so a free
 * copy here would have given the paid feature away.
 *
 * Its remaining two modules were verified as not worth rehoming: "Open bids"
 * was a summary card whose only job was to link to `/offers` (this screen
 * already carries the labelled Offers pill with a needs-you badge), and "Find
 * Collectors" sat behind COMMUNITY_GATED rendering nothing, duplicating the
 * unified search that `/search` already runs over users.
 */
import MemberMarketplace from '../listings';

export default function MarketTab() {
  return <MemberMarketplace asTab />;
}
