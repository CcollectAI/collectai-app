/**
 * Gamification API methods: profile, achievements, challenges, leaderboard.
 *
 * Response shapes match what gamification_router.py actually returns
 * (verified against live EC2 2026-04-30). Earlier types were aspirational
 * — `xp` / `streak_days` / `entries` / `earned` never existed on the
 * server side, so every gamification screen silently fell back to local
 * mock data.
 */
import { get } from "./httpClient";

export type GamificationProfile = {
  total_xp: number;
  level: number;
  current_xp: number;
  xp_to_next: number;
  current_streak: number;
  longest_streak: number;
  last_activity_date: string | null;
  weekly_xp: number;
  monthly_xp: number;
  achievements_unlocked: number;
  achievements_total: number;
};

export const getGamificationProfile = () =>
  get<{ profile: GamificationProfile }>("/gamification/profile");

export type PublicGamificationProfile = {
  user_id: string;
  total_xp: number;
  level: number;
  current_streak: number;
  achievements_unlocked: number;
  achievements_total: number;
  recent_achievements: {
    id: string;
    title: string;
    icon: string;
    tier: string;
    unlocked_at: string | null;
  }[];
};

export const getPublicGamificationProfile = (userId: string) =>
  get<{ profile: PublicGamificationProfile }>(
    `/gamification/profile/${encodeURIComponent(userId)}`,
  );

export type AchievementItem = {
  id: string;
  title: string;
  description: string;
  icon: string;
  category: string;
  xp_reward: number;
  tier: string;
  threshold: number;
  sort_order: number;
  unlocked: boolean;
  unlocked_at: string | null;
  progress: number;
};

export const getAchievements = (category?: string) =>
  get<{ achievements: AchievementItem[] }>(
    `/gamification/achievements${category ? `?category=${encodeURIComponent(category)}` : ""}`,
  );

export const getRecentAchievements = () =>
  get<{
    achievements: {
      id: string;
      title: string;
      tier: string;
      unlocked_at: string;
    }[];
  }>("/gamification/achievements/recent");

export const getActiveChallenges = () =>
  get<{
    challenges: {
      id: string;
      title: string;
      description: string;
      progress: number;
      target: number;
      reward_xp: number;
      expires_at: string | null;
    }[];
  }>("/gamification/challenges");

export type LeaderboardEntry = {
  rank: number;
  user_id: string;
  display_name: string | null;
  avatar_url: string | null;
  avatar_color: string | null;
  total_xp: number;
  level: number;
  current_streak: number;
};

// period: weekly | monthly | alltime (server param). The earlier signature
// passed `scope` / `category` — neither exists on the server.
export const getLeaderboard = (period?: "weekly" | "monthly" | "alltime") => {
  const sp = new URLSearchParams();
  if (period) sp.set("period", period);
  const q = sp.toString();
  return get<{
    leaderboard: LeaderboardEntry[];
    period: string;
    user_rank: number | null;
    total_count: number;
  }>(`/gamification/leaderboard${q ? `?${q}` : ""}`);
};
