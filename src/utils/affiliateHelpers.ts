import { Linking } from 'react-native';
import { track } from '@/analytics/track';
import { recordAffiliateClick } from '@/api/intelligenceApi';

type AffiliateLink = { source: string; url: string; affiliate_url: string; label: string };

// Map common hostnames → marketplace source slugs the backend understands.
// Best-effort; falls through to the raw hostname when no match.
const HOSTNAME_TO_SOURCE: Record<string, string> = {
  'www.ebay.com': 'ebay',
  'ebay.com': 'ebay',
  'www.tcgplayer.com': 'tcgplayer',
  'tcgplayer.com': 'tcgplayer',
  'www.cardmarket.com': 'cardmarket',
  'cardmarket.com': 'cardmarket',
  'www.mercari.com': 'mercari',
  'mercari.com': 'mercari',
  'www.discogs.com': 'discogs',
  'discogs.com': 'discogs',
  'stockx.com': 'stockx',
  'www.stockx.com': 'stockx',
  'www.bricklink.com': 'bricklink',
  'www.vinted.fr': 'vinted',
  'www.vinted.com': 'vinted',
  'vinted.com': 'vinted',
  'www.grailed.com': 'grailed',
  'grailed.com': 'grailed',
  'www.depop.com': 'depop',
  'depop.com': 'depop',
};

function hostnameToSource(hostname: string): string {
  return HOSTNAME_TO_SOURCE[hostname.toLowerCase()] ?? hostname.toLowerCase();
}

const FALLBACK_EBAY_SEARCH = 'https://www.ebay.com/sch/i.html?_nkw=';

// Common search query parameter names across marketplaces
const SEARCH_QUERY_PARAMS = ['_nkw', 'q', 'keyword', 'searchString', 's', 's_keywords', 'p'];

const ALLOWED_SCHEMES = ['http:', 'https:'];

/**
 * Build the best affiliate URL for a specific item, using pre-fetched category links.
 * Replaces the generic category search query in the URL with the item-specific name.
 */
export function buildItemAffiliateUrl(
  itemName: string,
  categoryAffiliateLinks: AffiliateLink[],
): string {
  if (categoryAffiliateLinks.length === 0) {
    return `${FALLBACK_EBAY_SEARCH}${encodeURIComponent(itemName)}`;
  }

  const link = categoryAffiliateLinks[0];
  const baseUrl = link.affiliate_url || link.url;

  try {
    const url = new URL(baseUrl);
    // Validate scheme to prevent open-redirect attacks
    if (!ALLOWED_SCHEMES.includes(url.protocol)) {
      return `${FALLBACK_EBAY_SEARCH}${encodeURIComponent(itemName)}`;
    }
    for (const key of SEARCH_QUERY_PARAMS) {
      if (url.searchParams.has(key)) {
        url.searchParams.set(key, itemName);
        return url.toString();
      }
    }
    // No known query param found — append as _nkw (eBay default)
    url.searchParams.set('_nkw', itemName);
    return url.toString();
  } catch {
    return `${FALLBACK_EBAY_SEARCH}${encodeURIComponent(itemName)}`;
  }
}

export function openAffiliateUrl(
  url: string,
  context?: { query?: string; item_key?: string; category?: string },
): void {
  // Only open HTTP(S) URLs
  let hostname = '';
  try {
    const parsed = new URL(url);
    if (!ALLOWED_SCHEMES.includes(parsed.protocol)) return;
    hostname = parsed.hostname;
  } catch {
    return;
  }
  track({ name: 'affiliate_link_opened', properties: { domain: hostname } });
  // Demand-side intelligence: record affiliate-click with marketplace source.
  // 7+ components route through this helper, so adding tracking here
  // propagates everywhere automatically. context is optional — call sites
  // that have query/item/category should pass them for richer signal.
  recordAffiliateClick({
    source: hostnameToSource(hostname),
    query: context?.query,
    item_key: context?.item_key,
    category: context?.category,
  });
  Linking.openURL(url).catch(() => {});
}
