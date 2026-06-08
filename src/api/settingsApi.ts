/**
 * Settings, preferences, and taxonomy API methods.
 */
import { get, put, patch, post, del } from "./httpClient";
import { followedCategoriesStore } from "@/data/followedCategoriesStore";

// Onboarding / category-follow state.
// PUT /settings only accepts {currency, region, locale} (user_settings_router.py)
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
