/**
 * Social API methods: user search, block/unblock.
 */
import { get, post, del } from "./httpClient";

export const searchUsers = (query: string, limit = 10) =>
  get<{
    users: Array<{
      user_id: string;
      display_name: string;
      handle: string | null;
      avatar_url: string | null;
    }>;
  }>(`/social/users/search?q=${encodeURIComponent(query)}&limit=${limit}`);

export const blockUser = (userId: string) =>
  post(`/social/block/${encodeURIComponent(userId)}`);

export const unblockUser = (userId: string) =>
  del(`/social/block/${encodeURIComponent(userId)}`);

export const listBlockedUsers = () =>
  get<{
    blocked: Array<{
      user_id: string;
      display_name: string | null;
      blocked_at: string;
    }>;
  }>("/social/blocked");
