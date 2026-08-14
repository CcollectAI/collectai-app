/**
 * Settings, preferences, and taxonomy API methods.
 */
import { get, put, patch, post, del } from "./httpClient";
import { followedCategoriesStore } from "@/data/followedCategoriesStore";

/**
 * Persist the user's region / currency / number-format locale.
 *
 * Use this instead of a raw `fetch` to `${API_BASE}/settings`. Four call sites
 * (onboarding, AppearanceSection ×2, ProfileEditSection) hand-rolled that fetch
 * and never read `res.ok` — and `fetch` RESOLVES on 4xx/5xx rather than
 * throwing, so the surrounding try/catch never fired and the failure left no
 * trace. A Korean user's `korea` / `KRW` / `ko-KR` was rejected by the DB CHECK
 * constraints (fixed 2026-07-30) and the app reported nothing at all.
 *
 * `put` throws on a non-2xx, so callers' existing catch blocks now work.
 * Server contract: `user_settings_router.py`.
 */
export const updateUserSettings = (payload: {
  currency?: string;
  region?: string;
  locale?: string;
  /**
   * 'beginner' | 'intermediate' | 'advanced'. Omit to leave it untouched — the
   * server COALESCEs, so a settings save that does not mention skill level
   * cannot erase it. There is deliberately NO way to clear it back to null from
   * the client: null means "never asked", and once asked, that is no longer
   * true.
   *
   * The value set here must exist in VALID_SKILL_LEVELS
   * (user_settings_router.py) AND in the CHECK from migration 20260814c. Those
   * two are one contract; sending a fourth value gets a 400, and would have
   * been a 500 if only the code had been widened — see the currency/region/
   * locale incident in docs/ARCHITECTURE.md.
   */
  skill_level?: string;
}) => put<{ success: boolean; settings: Record<string, unknown> }>('/settings', payload);

/**
 * Update the user's public profile. Same reasoning as `updateUserSettings`:
 * the raw-fetch version swallowed failures, so a rejected username (it is
 * UNIQUE) closed the edit modal and fired a *confirmation* haptic while the
 * change never landed.
 */
export const updateProfile = (payload: { username?: string; bio?: string }) =>
  patch<Record<string, unknown>>('/settings/profile', payload);

// Onboarding / category-follow state.
// PUT /settings accepts {currency, region, locale, skill_level} (user_settings_router.py)
// — `followed_categories` was silently dropped, so onboarding's "save my picks"
// did nothing and the home tab showed no follows. Wire to /events/categories/*
// which is the real follow store. Fanned-out PUT-style helper so the
// onboarding caller doesn't need to compute the diff itself.
export const saveFollowedCategories = async (categories: string[]) => {
  // Snapshot current follows, diff, then converge.
  const cur = await getFollowedCategories();
  const have = new Set(cur.followed_categories);
  const want = new Set(categories);
  const toAdd = [...want].filter((c) => !have.has(c));
  const toRemove = [...have].filter((c) => !want.has(c));
  await Promise.all([
    ...toAdd.map((c) => post(`/events/categories/${encodeURIComponent(c)}/follow`, {})),
    ...toRemove.map((c) => del(`/events/categories/${encodeURIComponent(c)}/follow`)),
  ]);
  // Keep the shared store (and every live consumer) in sync.
  followedCategoriesStore.setAll(categories);
  return { followed_categories: categories };
};

export const getFollowedCategories = async (): Promise<{ followed_categories: string[] }> => {
  // events_core.py:486 returns {categories: string[]}. Map to the legacy
  // shape this module has always advertised so callers don't break.
  const r = await get<{ categories?: string[] }>("/events/categories/followed");
  return { followed_categories: r?.categories ?? [] };
};

export const getAlertPreferences = () =>
  get<{
    price_drop_enabled: boolean;
    price_drop_threshold: number;
    new_listing_enabled: boolean;
    milestone_enabled: boolean;
    price_increase_enabled: boolean;
    price_increase_threshold: number;
    frequency: 'immediate' | 'daily' | 'weekly';
  }>("/settings/alert-preferences");

export const updateAlertPreferences = (prefs: {
  price_drop_enabled?: boolean;
  price_drop_threshold?: number;
  new_listing_enabled?: boolean;
  milestone_enabled?: boolean;
  price_increase_enabled?: boolean;
  price_increase_threshold?: number;
  frequency?: 'immediate' | 'daily' | 'weekly';
}) =>
  patch<{
    price_drop_enabled: boolean;
    price_drop_threshold: number;
    new_listing_enabled: boolean;
    milestone_enabled: boolean;
    price_increase_enabled: boolean;
    price_increase_threshold: number;
    frequency: 'immediate' | 'daily' | 'weekly';
  }>("/settings/alert-preferences", prefs as Record<string, unknown>);

// Taxonomy
export const getTaxonomy = () => get("/taxonomy/current");

export const getTaxonomyCategories = () =>
  get<{
    version: string;
    categories: {
      category_id: string;
      display_name: string;
      subtypes: string[];
      collections: string[];
    }[];
  }>("/taxonomy/categories");
