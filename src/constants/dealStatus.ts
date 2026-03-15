/**
 * Shared deal/offer status labels.
 *
 * Used by sell/offers.tsx, sell/[offerId].tsx, and any other screen displaying offer status.
 */

import type { OfferStatus } from '@/data/types';

export const STATUS_LABELS: Record<OfferStatus, string> = {
  proposed: 'Pending',
  countered: 'Countered',
  accepted: 'Accepted',
  declined: 'Declined',
  expired: 'Expired',
  completed: 'Completed',
  cancelled: 'Cancelled',
};
