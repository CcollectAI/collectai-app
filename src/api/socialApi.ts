/**
 * Social API methods: user search, block/unblock.
 */
import { get, post, del } from "./httpClient";

export const searchUsers = (query: string, limit = 10) =>
  get<{
    users: {
      user_id: string;
      display_name: string;
      handle: string | null;
      avatar_url: string | null;
    }[];
  }>(`/social/users/search?q=${encodeURIComponent(query)}&limit=${limit}`);

export const blockUser = (userId: string) =>
  post(`/social/block/${encodeURIComponent(userId)}`);

export const unblockUser = (userId: string) =>
  del(`/social/block/${encodeURIComponent(userId)}`);

export const listBlockedUsers = () =>
  get<{
    blocked: {
      user_id: string;
      display_name: string | null;
      blocked_at: string;
    }[];
  }>("/social/blocked");

export type CategoryLeaderboardEntry = {
  rank: number;
  user_id: string;
  display_name: string;
  handle: string | null;
  avatar_url: string | null;
  item_count: number;
  value_eur: number;
  /** Items carrying a photo, a condition AND a purchase price — all three.
   *  The second ranking axis for the 40+ categories that have no sold-comp
   *  source and therefore no meaningful value board. */
  documented_count: number;
  documented_pct: number;
  is_you: boolean;
};

/**
 * Top collectors in ONE category, ranked by items owned.
 *
 * Deliberately NOT `/gamification/leaderboard`: that ranks by XP, which has no
 * category dimension at all, and its UI is gated off behind
 * GAMIFICATION_UI_ENABLED because the number is not meaningful. This ranks on
 * something real.
 *
 * The server excludes anyone who turned off "Allow discovery" or "Show item
 * count" in Settings → Privacy, so a SHORT board is a correct board — never
 * treat a small row count as a failure or pad it.
 */
export const getCategoryLeaderboard = (
  categoryId: string,
  limit = 25,
  metric: 'items' | 'value' | 'documented' = 'items',
) =>
  get<{
    category: string;
    metric: string;
    leaderboard: CategoryLeaderboardEntry[];
    your_rank: number | null;
    total_ranked: number;
    /** FALSE => nobody on this board holds a comp-backed item, so a value
     *  ranking would sort a column of zeros. Server-MEASURED, not a category
     *  list, so it self-heals when a category gains or loses a price source. */
    value_ranking_available: boolean;
  }>(
    `/social/leaderboard/category/${encodeURIComponent(categoryId)}` +
      `?limit=${limit}&metric=${metric}`,
  );

/** One category a collector holds, plus where they place in it. */
export type CollectorCategoryStanding = {
  category_id: string;
  item_count: number;
  value_eur: number;
  /**
   * `null` means NOT RANKED, which is not the same as ranked last. The server
   * withholds a rank when the member is not discoverable or hides their item
   * count — rendering null as a number would state a placement nobody computed.
   */
  rank: number | null;
  total_ranked: number | null;
};

/**
 * What a collector collects, most-held category first, with their standing.
 *
 * Privacy is enforced SERVER-side and the client must not try to reconstruct
 * what was withheld: hidden counts arrive as 0 with a null rank, and hidden
 * values arrive as 0 with `value_visible: false` on the response. Those two
 * zeroes mean different things and the UI has to say so — "€0" and "hidden"
 * are not interchangeable.
 *
 * Viewing your OWN profile returns everything regardless of your switches.
 */
export const getCollectorCategories = (userId: string, limit = 12) =>
  get<{
    user_id: string;
    categories: CollectorCategoryStanding[];
    value_visible: boolean;
  }>(`/social/users/${encodeURIComponent(userId)}/categories?limit=${limit}`);
