/**
 * `/l/<listing id>` — the public short link for a marketplace listing.
 *
 * WHY THIS FILE EXISTS
 *
 * `_publish_supply_hook` writes `https://sparrowcollect.com/l/<uuid>` into
 * `market_hits.url`, and that is the right shape: it has to be an https link so
 * it still works when a seller shares it outside the app, and
 * `build_affiliate_url` rejects `sparrow://` outright.
 *
 * But nothing on this side ever handled it. There was no `/l` route, so a
 * universal link that DID open the app (iOS `associatedDomains` covers the whole
 * domain) landed on a 404 screen, and `sparrowcollect.com/l/<id>` returns 404 on
 * the web too — there is no web listing page. The single alert the marketplace
 * exists to produce (spec §1) had nowhere to go on any surface.
 *
 * This is a redirect rather than a second copy of the listing screen. Two
 * renderings of one thing is how they drift — `app/listing/[id].tsx` owns the
 * screen, and this owns only the URL shape.
 *
 * In-app taps do NOT come through here; `inAppListingHref` (src/lib/ids.ts)
 * turns the same URL into a `/listing/[id]` route directly, so the alert,
 * notification and push surfaces never round-trip through a redirect. This file
 * is for links arriving from OUTSIDE: a shared message, an email, a browser.
 */
import { Redirect, useLocalSearchParams } from 'expo-router';

import { isUuid } from '@/lib/ids';

export default function ListingShortLink() {
  const { id } = useLocalSearchParams<{ id?: string }>();

  // A malformed id must not reach /listing/[id]: the server would answer 22P02
  // on a non-uuid, which surfaces as a blank screen rather than as "not found".
  // Sending it to the marketplace instead is the honest degrade — the user
  // followed a listing link, so the marketplace is the nearest true thing.
  if (!isUuid(id)) return <Redirect href="/listings" />;

  return <Redirect href={{ pathname: '/listing/[id]', params: { id } }} />;
}
