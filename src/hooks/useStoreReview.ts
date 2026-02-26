/**
 * useStoreReview — conditionally prompts for App Store / Play Store review.
 *
 * Criteria (all must be met):
 * - User has 10+ items in collection
 * - App used on 3+ separate days
 * - Not prompted in the last 90 days
 *
 * Uses expo-store-review which shows the native in-app review dialog.
 */

import { useEffect, useCallback } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import logger from '@/utils/logger';

const DAYS_KEY = '@collectai/app_use_days';
const LAST_PROMPT_KEY = '@collectai/store_review_last_prompt';
const MIN_ITEMS = 10;
const MIN_DAYS = 3;
const COOLDOWN_MS = 90 * 24 * 60 * 60 * 1000; // 90 days

let StoreReview: { isAvailableAsync?: () => Promise<boolean>; requestReview?: () => Promise<void> } | null = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  StoreReview = require('expo-store-review');
} catch {
  // expo-store-review not installed — skip silently
}

/** Record today as an active use day. Call on app launch. */
async function recordActiveDay(): Promise<number> {
  const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
  const raw = await AsyncStorage.getItem(DAYS_KEY);
  const days: string[] = raw ? JSON.parse(raw) : [];
  if (!days.includes(today)) {
    days.push(today);
    await AsyncStorage.setItem(DAYS_KEY, JSON.stringify(days));
  }
  return days.length;
}

async function canPrompt(itemCount: number): Promise<boolean> {
  if (!StoreReview?.requestReview) return false;

  if (itemCount < MIN_ITEMS) return false;

  const activeDays = await recordActiveDay();
  if (activeDays < MIN_DAYS) return false;

  const lastPrompt = await AsyncStorage.getItem(LAST_PROMPT_KEY);
  if (lastPrompt) {
    const elapsed = Date.now() - Number(lastPrompt);
    if (elapsed < COOLDOWN_MS) return false;
  }

  // Check native availability
  if (StoreReview.isAvailableAsync) {
    const available = await StoreReview.isAvailableAsync();
    if (!available) return false;
  }

  return true;
}

/**
 * Hook that checks review eligibility and prompts when criteria are met.
 * @param itemCount - Number of items in the user's collection.
 */
export function useStoreReview(itemCount: number) {
  const maybePrompt = useCallback(async () => {
    try {
      const eligible = await canPrompt(itemCount);
      if (!eligible) return;

      await StoreReview!.requestReview!();
      await AsyncStorage.setItem(LAST_PROMPT_KEY, String(Date.now()));
      logger.info('[StoreReview] Review prompt shown');
    } catch (err) {
      logger.warn('[StoreReview] Failed to prompt:', err);
    }
  }, [itemCount]);

  useEffect(() => {
    // Small delay so it doesn't block initial render
    const timer = setTimeout(maybePrompt, 3000);
    return () => clearTimeout(timer);
  }, [maybePrompt]);
}

/** Record an active day without triggering a review prompt. */
export { recordActiveDay };
