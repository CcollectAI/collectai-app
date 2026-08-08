/**
 * Pins the routing decision for OUR OWN marketplace listing links.
 *
 * The bug this exists to stop coming back: `_publish_supply_hook` writes
 * `https://sparrowcollect.com/l/<uuid>` into `market_hits.url`, and all three
 * consumers treated "starts with https" as "external" —
 *
 *   app/alerts.tsx           -> Linking.openURL
 *   app/notifications.tsx    -> openAffiliateUrl
 *   usePushNotifications.ts  -> Linking.openURL
 *
 * so the one alert the marketplace exists to produce sent the user out to a web
 * page that returns 404. Nothing went red; it just silently left the app.
 *
 * The important assertions here are the NEGATIVE ones. Returning a route for an
 * eBay or Cardmarket URL would be far worse than the original bug — those must
 * open externally, and swallowing them would break every non-Sparrow Target Hit
 * at once.
 */
import { inAppListingHref } from '../../src/lib/ids';

const LISTING_ID = '1bd83bb3-bd79-45ae-8ae7-a7c0470b5ec8';

describe('inAppListingHref', () => {
  it('routes our own listing URL to the in-app listing screen', () => {
    expect(inAppListingHref(`https://sparrowcollect.com/l/${LISTING_ID}`)).toEqual({
      pathname: '/listing/[id]',
      params: { id: LISTING_ID },
    });
  });

  it('accepts the www host, http, a trailing slash and surrounding whitespace', () => {
    // Real URLs arrive from a JSONB column and a push payload, not from a
    // constant — any of these would otherwise fall through to the browser.
    for (const url of [
      `https://www.sparrowcollect.com/l/${LISTING_ID}`,
      `http://sparrowcollect.com/l/${LISTING_ID}`,
      `https://sparrowcollect.com/l/${LISTING_ID}/`,
      `  https://sparrowcollect.com/l/${LISTING_ID}  `,
      `https://SparrowCollect.com/L/${LISTING_ID.toUpperCase()}`,
    ]) {
      expect(inAppListingHref(url)).not.toBeNull();
    }
  });

  it('does NOT capture other marketplaces — they must still open externally', () => {
    for (const url of [
      'https://www.ebay.com/itm/123456789',
      'https://www.cardmarket.com/en/Magic/Products/Singles/Legends/Bayou',
      'https://www.bricklink.com/v2/catalog/catalogitem.page?S=75192-1',
      // Lookalike hosts. A substring check would hand an attacker's page an
      // in-app route, and a phishing listing that renders as OUR screen is a
      // worse outcome than any bug this file is about.
      `https://sparrowcollect.com.evil.tld/l/${LISTING_ID}`,
      `https://notsparrowcollect.com/l/${LISTING_ID}`,
      `https://evil.tld/https://sparrowcollect.com/l/${LISTING_ID}`,
    ]) {
      expect(inAppListingHref(url)).toBeNull();
    }
  });

  it('rejects our host with a non-listing path', () => {
    for (const url of [
      'https://sparrowcollect.com/item/abc',
      'https://sparrowcollect.com/l/',
      `https://sparrowcollect.com/l/${LISTING_ID}/extra`,
    ]) {
      expect(inAppListingHref(url)).toBeNull();
    }
  });

  it('rejects a well-shaped path whose id is not a uuid', () => {
    // The regex is deliberately loose ([0-9a-f-]{36}) and isUuid does the real
    // check. Without that second gate, 36 hyphens would route into
    // /listing/[id] and the server would answer 22P02 — a blank screen rather
    // than an honest "not found".
    expect(inAppListingHref('https://sparrowcollect.com/l/------------------------------------')).toBeNull();
    expect(inAppListingHref('https://sparrowcollect.com/l/not-a-uuid')).toBeNull();
  });

  it('handles null, undefined and non-strings without throwing', () => {
    // triggerValue is JSONB and deep_link is nullable, so these reach it.
    expect(inAppListingHref(null)).toBeNull();
    expect(inAppListingHref(undefined)).toBeNull();
    expect(inAppListingHref('')).toBeNull();
    expect(inAppListingHref(42 as unknown as string)).toBeNull();
  });
});
