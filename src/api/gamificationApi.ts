/**
 * Gamification API methods: profile, achievements, challenges, leaderboard.
 */
import { get } from "./httpClient";

export const getGamificationProfile = () =>
  get<{
    user_id: string;
    xp: number;
    level: number;
    streak_days: number;
    badges: string[];
  }>("/gamification/profile");

export const getPublicGamificationProfile = (userId: string) =>
  get<{
    profile: {
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
  }>(`/gamification/profile/${encodeURIComponent(userId)}`);

export const getAchievements = () =>
  get<{
    achievements: {
      id: string;
      title: string;
      description: string;
      tier: string;
      earned: boolean;
      earned_at: string | null;
    }[];
  }>("/gamification/achievements");

export const getRecentAchievements = () =>
  get<{
    achievements: {
      id: string;
      title: string;
      tier: string;
      earned_at: string;
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

export const getLeaderboard = (scope?: string, category?: string) => {
  const sp = new URLSearchParams();
  if (scope) sp.set("scope", scope);
  if (category) sp.set("category", category);
  const q = sp.toString();
  return get<{
    entries: {
      rank: number;
      user_id: string;
      display_name: string;
      xp: number;
      level: number;
      avatar_url: string | null;
    }[];
  }>(`/gamification/leaderboard${q ? `?${q}` : ""}`);
};
