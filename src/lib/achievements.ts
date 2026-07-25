/**
 * Achievements System
 *
 * Tracks collector milestones and awards badges for accomplishments.
 * Achievements are computed from portfolio data and activity.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { logger } from '@/lib/logger';

// Achievement definitions
export interface Achievement {
  id: string;
  title: string;
  description: string;
  icon: string; // Ionicons name
  category: 'collection' | 'value' | 'activity' | 'social';
  tier: 'bronze' | 'silver' | 'gold' | 'platinum';
  condition: (stats: PortfolioStats) => boolean;
  progress?: (stats: PortfolioStats) => { current: number; target: number };
}

export interface PortfolioStats {
  itemCount: number;
  totalValue: number;
  categoryCount: number;
  scanCount: number;
  streakDays: number;
  feedbackCount: number;
  joinedDaysAgo: number;
}

export interface EarnedAchievement {
  achievementId: string;
  earnedAt: string;
  notified: boolean;
}

// Achievement catalog
export const ACHIEVEMENTS: Achievement[] = [
  // Collection size milestones
  {
    id: 'first_item',
    title: 'First Steps',
    description: 'Add your first item to the collection',
    icon: 'star-outline',
    category: 'collection',
    tier: 'bronze',
    condition: (s) => s.itemCount >= 1,
  },
  {
    id: 'collector_10',
    title: 'Budding Collector',
    description: 'Reach 10 items in your collection',
    icon: 'albums-outline',
    category: 'collection',
    tier: 'bronze',
    condition: (s) => s.itemCount >= 10,
    progress: (s) => ({ current: Math.min(s.itemCount, 10), target: 10 }),
  },
  {
    id: 'collector_50',
    title: 'Dedicated Collector',
    description: 'Reach 50 items in your collection',
    icon: 'albums',
    category: 'collection',
    tier: 'silver',
    condition: (s) => s.itemCount >= 50,
    progress: (s) => ({ current: Math.min(s.itemCount, 50), target: 50 }),
  },
  {
    id: 'collector_100',
    title: 'Serious Collector',
    description: 'Reach 100 items in your collection',
    icon: 'trophy-outline',
    category: 'collection',
    tier: 'gold',
    condition: (s) => s.itemCount >= 100,
    progress: (s) => ({ current: Math.min(s.itemCount, 100), target: 100 }),
  },
  {
    id: 'collector_500',
    title: 'Master Collector',
    description: 'Reach 500 items in your collection',
    icon: 'trophy',
    category: 'collection',
    tier: 'platinum',
    condition: (s) => s.itemCount >= 500,
    progress: (s) => ({ current: Math.min(s.itemCount, 500), target: 500 }),
  },

  // Value milestones
  {
    id: 'value_100',
    title: 'Getting Started',
    description: 'Portfolio value reaches €100',
    icon: 'wallet-outline',
    category: 'value',
    tier: 'bronze',
    condition: (s) => s.totalValue >= 100,
  },
  {
    id: 'value_1000',
    title: 'Four Figures',
    description: 'Portfolio value reaches €1,000',
    icon: 'cash-outline',
    category: 'value',
    tier: 'silver',
    condition: (s) => s.totalValue >= 1000,
    progress: (s) => ({ current: Math.min(s.totalValue, 1000), target: 1000 }),
  },
  {
    id: 'value_5000',
    title: 'Serious Investment',
    description: 'Portfolio value reaches €5,000',
    icon: 'diamond-outline',
    category: 'value',
    tier: 'gold',
    condition: (s) => s.totalValue >= 5000,
    progress: (s) => ({ current: Math.min(s.totalValue, 5000), target: 5000 }),
  },
  {
    id: 'value_10000',
    title: 'Five Figures',
    description: 'Portfolio value reaches €10,000',
    icon: 'diamond',
    category: 'value',
    tier: 'platinum',
    condition: (s) => s.totalValue >= 10000,
    progress: (s) => ({ current: Math.min(s.totalValue, 10000), target: 10000 }),
  },

  // Diversity milestones
  {
    id: 'diverse_3',
    title: 'Branching Out',
    description: 'Collect items from 3 different categories',
    icon: 'grid-outline',
    category: 'collection',
    tier: 'bronze',
    condition: (s) => s.categoryCount >= 3,
    progress: (s) => ({ current: Math.min(s.categoryCount, 3), target: 3 }),
  },
  {
    id: 'diverse_5',
    title: 'Well Rounded',
    description: 'Collect items from 5 different categories',
    icon: 'grid',
    category: 'collection',
    tier: 'silver',
    condition: (s) => s.categoryCount >= 5,
    progress: (s) => ({ current: Math.min(s.categoryCount, 5), target: 5 }),
  },

  // Activity milestones
  {
    id: 'scanner_10',
    title: 'Quick Scanner',
    description: 'Scan 10 items with QuickScan',
    icon: 'scan-outline',
    category: 'activity',
    tier: 'bronze',
    condition: (s) => s.scanCount >= 10,
    progress: (s) => ({ current: Math.min(s.scanCount, 10), target: 10 }),
  },
  {
    id: 'scanner_50',
    title: 'Scan Expert',
    description: 'Scan 50 items with QuickScan',
    icon: 'scan',
    category: 'activity',
    tier: 'silver',
    condition: (s) => s.scanCount >= 50,
    progress: (s) => ({ current: Math.min(s.scanCount, 50), target: 50 }),
  },
  {
    id: 'streak_7',
    title: 'Weekly Warrior',
    description: 'Use the app 7 days in a row',
    icon: 'flame-outline',
    category: 'activity',
    tier: 'bronze',
    condition: (s) => s.streakDays >= 7,
    progress: (s) => ({ current: Math.min(s.streakDays, 7), target: 7 }),
  },
  {
    id: 'streak_30',
    title: 'Monthly Master',
    description: 'Use the app 30 days in a row',
    icon: 'flame',
    category: 'activity',
    tier: 'gold',
    condition: (s) => s.streakDays >= 30,
    progress: (s) => ({ current: Math.min(s.streakDays, 30), target: 30 }),
  },

  // Contribution milestones
  {
    id: 'feedback_5',
    title: 'Helpful Hand',
    description: 'Submit 5 price feedback entries',
    icon: 'chatbubble-outline',
    category: 'social',
    tier: 'bronze',
    condition: (s) => s.feedbackCount >= 5,
    progress: (s) => ({ current: Math.min(s.feedbackCount, 5), target: 5 }),
  },
  {
    id: 'feedback_20',
    title: 'Community Contributor',
    description: 'Submit 20 price feedback entries',
    icon: 'chatbubbles',
    category: 'social',
    tier: 'silver',
    condition: (s) => s.feedbackCount >= 20,
    progress: (s) => ({ current: Math.min(s.feedbackCount, 20), target: 20 }),
  },
];

// Storage key
const ACHIEVEMENTS_KEY = '@collectai_achievements';
const STATS_KEY = '@collectai_stats';

/**
 * Load earned achievements from storage.
 */
export async function loadEarnedAchievements(): Promise<EarnedAchievement[]> {
  try {
    const stored = await AsyncStorage.getItem(ACHIEVEMENTS_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch (e) {
    logger.error('[silent-catch] achievements.ts:230:', e);
    return [];
  }
}

/**
 * Save earned achievement to storage.
 */
export async function saveEarnedAchievement(achievement: EarnedAchievement): Promise<void> {
  const current = await loadEarnedAchievements();
  if (current.some((a) => a.achievementId === achievement.achievementId)) {
    return; // Already earned
  }
  current.push(achievement);
  await AsyncStorage.setItem(ACHIEVEMENTS_KEY, JSON.stringify(current));
}

/**
 * Check portfolio stats against achievements and return newly earned ones.
 */
export async function checkAchievements(stats: PortfolioStats): Promise<Achievement[]> {
  const earned = await loadEarnedAchievements();
  const earnedIds = new Set(earned.map((e) => e.achievementId));

  const newlyEarned: Achievement[] = [];

  for (const achievement of ACHIEVEMENTS) {
    if (earnedIds.has(achievement.id)) continue;
    if (achievement.condition(stats)) {
      newlyEarned.push(achievement);
      await saveEarnedAchievement({
        achievementId: achievement.id,
        earnedAt: new Date().toISOString(),
        notified: false,
      });
    }
  }

  return newlyEarned;
}

/**
 * Get all achievements with earned status.
 */
export async function getAllAchievementsWithStatus(): Promise<
  (Achievement & { earned: boolean; earnedAt?: string })[]
> {
  const earned = await loadEarnedAchievements();
  const earnedMap = new Map(earned.map((e) => [e.achievementId, e]));

  return ACHIEVEMENTS.map((a) => ({
    ...a,
    earned: earnedMap.has(a.id),
    earnedAt: earnedMap.get(a.id)?.earnedAt,
  }));
}

/**
 * Get tier color for display.
 */
export function getTierColor(tier: Achievement['tier']): string {
  switch (tier) {
    case 'bronze':
      return '#CD7F32';
    case 'silver':
      return '#C0C0C0';
    case 'gold':
      return '#FFD700';
    case 'platinum':
      return '#E5E4E2';
    default:
      return '#9CA3AF';
  }
}

/**
 * Format tier for display.
 */
export function formatTier(tier: Achievement['tier']): string {
  return tier.charAt(0).toUpperCase() + tier.slice(1);
}
