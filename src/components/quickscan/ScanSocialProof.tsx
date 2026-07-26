/**
 * ScanSocialProof — Feature-flag-gated wrapper for SocialProofSection
 * on the QuickScan result screen. Shows collector count, trending status,
 * recent sold items, and scarcity data.
 */

import React from 'react';
import { useScannerTheme } from '@/hooks/useAppTheme';
import { featureFlags } from '@/config/featureFlags';
import { SocialProofSection } from '@/components/SocialProofSection';
import type { SocialProof, CurrencyCode } from '@/data/types';

type Props = {
  socialProof?: SocialProof | null;
  currency: CurrencyCode;
};

function ScanSocialProofInner({ socialProof, currency }: Props) {
  if (!featureFlags.FEATURE_SOCIAL_PROOF || !socialProof) return null;

  return <SocialProofSection socialProof={socialProof} currency={currency} />;
}

export const ScanSocialProof = React.memo(ScanSocialProofInner);
