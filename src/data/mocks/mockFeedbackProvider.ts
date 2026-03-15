/**
 * Mock feedback domain provider.
 */

import { logger } from '@/lib/logger';

export async function submitFeedback(
  itemId: string,
  feedbackType: 'sale_price' | 'disagree' | 'accurate',
  value?: string,
): Promise<{ success: boolean; feedbackId?: string }> {
  const feedbackId = `feedback-mock-${Date.now()}`;
  logger.info('[MockDataProvider] submitFeedback', { itemId, feedbackType, value, feedbackId });
  return { success: true, feedbackId };
}

export async function submitCorrection(
  itemId: string,
  corrections: {
    correctedPrice?: number;
    correctedCondition?: string;
    correctedCategory?: string;
    notes?: string;
  },
): Promise<{ success: boolean }> {
  logger.info('[MockDataProvider] submitCorrection', { itemId, corrections });
  return { success: true };
}
