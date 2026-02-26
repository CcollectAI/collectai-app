import { Linking } from 'react-native';

type AffiliateLink = { source: string; url: string; affiliate_url: string; label: string };

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

export function openAffiliateUrl(url: string): void {
  // Only open HTTP(S) URLs
  try {
    const parsed = new URL(url);
    if (!ALLOWED_SCHEMES.includes(parsed.protocol)) return;
  } catch {
    return;
  }
  Linking.openURL(url).catch(() => {});
}
