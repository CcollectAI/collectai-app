/**
 * Settings, preferences, and taxonomy API methods.
 */
import { get, put, patch } from "./httpClient";

// Onboarding / User Settings
export const saveFollowedCategories = (categories: string[]) =>
  put("/settings", { followed_categories: categories });

export const getFollowedCategories = () =>
  get<{ followed_categories: string[] }>("/settings");

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
    categories: Array<{
      category_id: string;
      display_name: string;
      subtypes: string[];
      collections: string[];
    }>;
  }>("/taxonomy/categories");
