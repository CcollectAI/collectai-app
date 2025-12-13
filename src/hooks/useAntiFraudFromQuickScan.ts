import { useMemo } from 'react';
import {
  AntiFraudInput,
  AntiFraudResult,
  computeAntiFraudSignal,
  QuickScanPrediction,
} from '@/utils/antiFraud';

/**
 * Helper hook that turns QuickScan + asking price into an AntiFraudResult.
 *
 * quickscan:
 *   prediction: { estimated_mid, estimated_low, estimated_high, currency, confidence }
 * askingPrice:
 *   numeric user input in same currency.
 * costBasis:
 *   optional if user is scanning something they already own.
 */
export function useAntiFraudFromQuickScan(
  quickscan: QuickScanPrediction | null,
  askingPrice: number | null | undefined,
  costBasis?: number | null,
): AntiFraudResult | null {
  return useMemo(() => {
    if (!quickscan) return null;

    const input: AntiFraudInput = {
      prediction: quickscan,
      askingPrice:
        askingPrice != null && Number.isFinite(askingPrice)
          ? askingPrice
          : null,
      costBasis:
        costBasis != null && Number.isFinite(costBasis)
          ? costBasis
          : null,
    };

    return computeAntiFraudSignal(input);
  }, [quickscan, askingPrice, costBasis]);
}
