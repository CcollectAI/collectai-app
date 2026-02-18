/**
 * Deep linking utilities for CollectAI.
 *
 * Provides helpers to generate shareable URLs for items and events.
 * Each helper returns both a universal link (HTTPS, for web + app) and
 * a custom-scheme deep link (collectai://, for direct app open).
 *
 * Universal links require the Apple App Site Association / Android
 * assetlinks.json to be served from the web domain.
 */

/** The custom URL scheme registered in app.json */
const APP_SCHEME = 'collectai';

/**
 * The web domain used for universal links.
 * Update this when the production domain is finalised.
 */
const WEB_DOMAIN = 'https://collectai.app';

export interface ShareUrls {
  /** HTTPS universal link — works on web and triggers app open when installed */
  webUrl: string;
  /** Custom-scheme deep link — opens directly in the app */
  deepLink: string;
}

/**
 * Generate share URLs for a collection item.
 *
 * Maps to route: app/item/[id].tsx
 *
 * @param itemId - The unique item identifier (UUID)
 * @returns An object with webUrl and deepLink strings
 *
 * @example
 * ```ts
 * const urls = getItemShareUrl('abc-123');
 * // urls.webUrl   === 'https://collectai.app/item/abc-123'
 * // urls.deepLink === 'collectai://item/abc-123'
 * ```
 */
export function getItemShareUrl(itemId: string): ShareUrls {
  return {
    webUrl: `${WEB_DOMAIN}/item/${encodeURIComponent(itemId)}`,
    deepLink: `${APP_SCHEME}://item/${encodeURIComponent(itemId)}`,
  };
}

/**
 * Generate share URLs for an event.
 *
 * Maps to route: app/events/[eventId].tsx
 *
 * @param eventId - The unique event identifier (UUID)
 * @returns An object with webUrl and deepLink strings
 *
 * @example
 * ```ts
 * const urls = getEventShareUrl('evt-456');
 * // urls.webUrl   === 'https://collectai.app/events/evt-456'
 * // urls.deepLink === 'collectai://events/evt-456'
 * ```
 */
export function getEventShareUrl(eventId: string): ShareUrls {
  return {
    webUrl: `${WEB_DOMAIN}/events/${encodeURIComponent(eventId)}`,
    deepLink: `${APP_SCHEME}://events/${encodeURIComponent(eventId)}`,
  };
}

/**
 * Generate share URLs for a category page.
 *
 * Maps to route: app/categories/[categoryId].tsx
 */
export function getCategoryShareUrl(categoryId: string): ShareUrls {
  return {
    webUrl: `${WEB_DOMAIN}/categories/${encodeURIComponent(categoryId)}`,
    deepLink: `${APP_SCHEME}://categories/${encodeURIComponent(categoryId)}`,
  };
}

/**
 * Generate share URLs for a deal.
 *
 * Maps to route: app/purchase/deal/[dealId].tsx
 */
export function getDealShareUrl(dealId: string): ShareUrls {
  return {
    webUrl: `${WEB_DOMAIN}/purchase/deal/${encodeURIComponent(dealId)}`,
    deepLink: `${APP_SCHEME}://purchase/deal/${encodeURIComponent(dealId)}`,
  };
}

/**
 * Generate share URLs for a user profile.
 *
 * Maps to route: app/users/[userId].tsx
 */
export function getUserShareUrl(userId: string): ShareUrls {
  return {
    webUrl: `${WEB_DOMAIN}/users/${encodeURIComponent(userId)}`,
    deepLink: `${APP_SCHEME}://users/${encodeURIComponent(userId)}`,
  };
}
