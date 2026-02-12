import client from '@/services/collectorsClient';
import type { AntiFraudResult } from '@/utils/antiFraud';
import { logger } from '@/lib/logger';

export type AntiFraudUserDecision = 'proceed' | 'negotiate' | 'avoid';

export interface AntiFraudEventPayload {
  item_name?: string | null;
  category?: string | null;
  quickscan_id?: string | null;
  risk: string;
  score: number;
  decision: AntiFraudUserDecision;
  asking_price?: number | null;
  estimated_mid?: number | null;
  currency?: string | null;
}

/**
 * Log an anti-fraud decision to the backend.
 * Backend route (to be implemented): POST /anti-fraud/events
 */
export async function logAntiFraudEvent(
  payload: AntiFraudEventPayload,
): Promise<void> {
  try {
    await client.post('/anti-fraud/events', payload);
  } catch (e) {
    logger.warn('[antiFraudClient] logAntiFraudEvent failed', e);
  }
}

/**
 * Convenience builder from raw result + context.
 */
export function buildAntiFraudEventFromResult(opts: {
  result: AntiFraudResult;
  decision: AntiFraudUserDecision;
  itemName?: string | null;
  category?: string | null;
  quickscanId?: string | null;
  currency?: string | null;
}): AntiFraudEventPayload {
  const { result, decision, itemName, category, quickscanId, currency } = opts;
  return {
    item_name: itemName ?? null,
    category: category ?? null,
    quickscan_id: quickscanId ?? null,
    risk: result.risk,
    score: result.score,
    decision,
    asking_price: result.details.askingPrice ?? null,
    estimated_mid: result.details.estimatedMid ?? null,
    currency: currency ?? null,
  };
}
