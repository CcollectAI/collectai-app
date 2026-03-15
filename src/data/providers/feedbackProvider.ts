/**
 * Feedback domain provider — price feedback and corrections.
 */

import { collectorsApi } from '../../api/collectorsApi';
import logger from '../../utils/logger';

export async function submitFeedback(
  itemId: string,
  feedbackType: 'sale_price' | 'disagree' | 'accurate',
  value?: string,
): Promise<{ success: boolean; feedbackId?: string }> {
  try {
    const res = await collectorsApi.submitFeedback({
      item_id: itemId,
      feedback_type: feedbackType,
      value,
    }) as Record<string, unknown>;
    return {
      success: (res.success as boolean | undefined) ?? true,
      feedbackId: res.feedback_id as string | undefined,
    };
  } catch (err: unknown) {
    logger.error('[SupabaseDataProvider] submitFeedback error:', err);
    throw new Error(err instanceof Error ? err.message : 'Failed to submit feedback');
  }
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
  try {
    const res = await collectorsApi.submitCorrection({
      item_id: itemId,
      corrected_price: corrections.correctedPrice,
      corrected_condition: corrections.correctedCondition,
      corrected_category: corrections.correctedCategory,
      notes: corrections.notes,
    }) as Record<string, unknown>;
    return { success: (res.success as boolean | undefined) ?? true };
  } catch (err: unknown) {
    logger.error('[SupabaseDataProvider] submitCorrection error:', err);
    throw new Error(err instanceof Error ? err.message : 'Failed to submit correction');
  }
}
