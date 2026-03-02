/**
 * useListForSale — Hook for the multi-marketplace listing modal.
 *
 * Manages modal state, per-marketplace price/selection, fee calculation,
 * and submission of listings to the backend.
 */

import { useState, useCallback, useMemo } from 'react';
import { dataProvider } from '@/data';
import type {
  MarketplaceId,
  ListingFormat,
  MarketplaceFeeSchedule,
  CurrencyCode,
} from '@/data/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ConditionLabel = 'Mint' | 'Near Mint' | 'Good' | 'Fair' | 'Poor';

export type MarketplaceOption = {
  id: MarketplaceId;
  label: string;
  icon: string; // Ionicons glyph name
  color: string;
  defaultFeePct: number; // fallback if server schedules haven't loaded
};

export type PerMarketplaceState = {
  selected: boolean;
  price: string; // raw text input
};

export type FeeBreakdown = {
  marketplaceId: MarketplaceId;
  price: number;
  baseFee: number;
  processingFee: number;
  fixedFee: number;
  totalFees: number;
  netProceeds: number;
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** The six marketplaces shown in the modal, with visual config + fallback fees. */
export const MARKETPLACE_OPTIONS: MarketplaceOption[] = [
  { id: 'collectai', label: 'CollectAI P2P', icon: 'people-outline',          color: '#81D8D0', defaultFeePct: 5.0 },
  { id: 'ebay',      label: 'eBay',          icon: 'cart-outline',            color: '#E53238', defaultFeePct: 12.9 },
  { id: 'mercari',   label: 'Mercari',       icon: 'storefront-outline',      color: '#4DC8F0', defaultFeePct: 10.0 },
  { id: 'cardmarket',label: 'Cardmarket',    icon: 'card-outline',            color: '#1A3C7D', defaultFeePct: 5.0 },
  { id: 'stockx',    label: 'StockX',        icon: 'trending-up-outline',     color: '#006340', defaultFeePct: 9.5 },
  { id: 'bricklink', label: 'BrickLink',     icon: 'cube-outline',            color: '#D01012', defaultFeePct: 3.0 },
];

export const LISTING_FORMATS: { value: ListingFormat; label: string }[] = [
  { value: 'fixed_price', label: 'Fixed Price' },
  { value: 'auction',     label: 'Auction' },
  { value: 'best_offer',  label: 'Best Offer' },
];

export const CONDITION_LABELS: ConditionLabel[] = [
  'Mint',
  'Near Mint',
  'Good',
  'Fair',
  'Poor',
];

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useListForSale(opts: {
  itemId: string;
  itemName: string;
  currency: CurrencyCode;
  suggestedPrice?: number;
}) {
  const { itemId, itemName, currency, suggestedPrice } = opts;

  // Modal visibility
  const [visible, setVisible] = useState(false);

  // Per-marketplace state (selection + price)
  const defaultPrice = suggestedPrice ? String(Math.round(suggestedPrice)) : '';
  const [marketplaces, setMarketplaces] = useState<Record<MarketplaceId, PerMarketplaceState>>(() => {
    const initial: Partial<Record<MarketplaceId, PerMarketplaceState>> = {};
    for (const mp of MARKETPLACE_OPTIONS) {
      initial[mp.id] = { selected: false, price: defaultPrice };
    }
    return initial as Record<MarketplaceId, PerMarketplaceState>;
  });

  // Listing config
  const [format, setFormat] = useState<ListingFormat>('fixed_price');
  const [condition, setCondition] = useState<ConditionLabel>('Good');

  // Server fee schedules (loaded once when modal opens)
  const [feeSchedules, setFeeSchedules] = useState<MarketplaceFeeSchedule[]>([]);
  const [feeSchedulesLoaded, setFeeSchedulesLoaded] = useState(false);

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selected marketplace IDs
  const selectedIds = useMemo(
    () => MARKETPLACE_OPTIONS.filter((mp) => marketplaces[mp.id]?.selected).map((mp) => mp.id),
    [marketplaces],
  );

  // ── Open / Close ──────────────────────────────────────────────────────

  const open = useCallback(() => {
    // Reset to defaults when opening
    const newMp: Partial<Record<MarketplaceId, PerMarketplaceState>> = {};
    const dp = suggestedPrice ? String(Math.round(suggestedPrice)) : '';
    for (const mp of MARKETPLACE_OPTIONS) {
      newMp[mp.id] = { selected: false, price: dp };
    }
    setMarketplaces(newMp as Record<MarketplaceId, PerMarketplaceState>);
    setFormat('fixed_price');
    setCondition('Good');
    setError(null);
    setSubmitting(false);
    setVisible(true);

    // Load fee schedules from server (non-blocking)
    if (!feeSchedulesLoaded) {
      dataProvider
        .getMarketplaceFeeSchedules()
        .then((schedules) => {
          setFeeSchedules(schedules);
          setFeeSchedulesLoaded(true);
        })
        .catch(() => {
          // Fall back to client-side defaults — not critical
        });
    }
  }, [suggestedPrice, feeSchedulesLoaded]);

  const close = useCallback(() => {
    setVisible(false);
  }, []);

  // ── Toggle / Update marketplace ───────────────────────────────────────

  const toggleMarketplace = useCallback((mpId: MarketplaceId) => {
    setMarketplaces((prev) => ({
      ...prev,
      [mpId]: { ...prev[mpId], selected: !prev[mpId].selected },
    }));
  }, []);

  const setMarketplacePrice = useCallback((mpId: MarketplaceId, price: string) => {
    setMarketplaces((prev) => ({
      ...prev,
      [mpId]: { ...prev[mpId], price },
    }));
  }, []);

  // ── Fee Calculation ───────────────────────────────────────────────────

  const calculateFee = useCallback(
    (mpId: MarketplaceId, priceStr: string): FeeBreakdown | null => {
      const price = parseFloat(priceStr.replace(/[^\d.]/g, ''));
      if (!Number.isFinite(price) || price <= 0) return null;

      // Try server schedule first
      const serverSchedule = feeSchedules.find((s) => s.marketplaceId === mpId);
      if (serverSchedule) {
        const baseFee = price * serverSchedule.baseFeePct / 100;
        const processingFee = price * serverSchedule.paymentProcessingPct / 100;
        const fixedFee = serverSchedule.fixedFee;
        const totalFees = Math.round((baseFee + processingFee + fixedFee) * 100) / 100;
        return {
          marketplaceId: mpId,
          price,
          baseFee: Math.round(baseFee * 100) / 100,
          processingFee: Math.round(processingFee * 100) / 100,
          fixedFee,
          totalFees,
          netProceeds: Math.round((price - totalFees) * 100) / 100,
        };
      }

      // Fallback to client-side estimate
      const option = MARKETPLACE_OPTIONS.find((o) => o.id === mpId);
      const feePct = option?.defaultFeePct ?? 5;
      const totalFees = Math.round(price * feePct / 100 * 100) / 100;
      return {
        marketplaceId: mpId,
        price,
        baseFee: totalFees,
        processingFee: 0,
        fixedFee: 0,
        totalFees,
        netProceeds: Math.round((price - totalFees) * 100) / 100,
      };
    },
    [feeSchedules],
  );

  /** Fee breakdowns for all selected marketplaces. */
  const feeBreakdowns = useMemo(() => {
    const results: FeeBreakdown[] = [];
    for (const mpId of selectedIds) {
      const state = marketplaces[mpId];
      if (!state) continue;
      const breakdown = calculateFee(mpId, state.price);
      if (breakdown) results.push(breakdown);
    }
    return results;
  }, [selectedIds, marketplaces, calculateFee]);

  // ── Submission ────────────────────────────────────────────────────────

  const canSubmit = selectedIds.length > 0 && selectedIds.every((mpId) => {
    const price = parseFloat((marketplaces[mpId]?.price ?? '').replace(/[^\d.]/g, ''));
    return Number.isFinite(price) && price > 0;
  });

  const submit = useCallback(async (): Promise<boolean> => {
    if (!canSubmit || submitting) return false;
    setSubmitting(true);
    setError(null);

    try {
      // Create a listing for each selected marketplace (sequentially to avoid rate limiting)
      for (const mpId of selectedIds) {
        const state = marketplaces[mpId];
        const price = parseFloat((state?.price ?? '').replace(/[^\d.]/g, ''));
        const fee = calculateFee(mpId, state?.price ?? '');

        await dataProvider.createMarketplaceListing({
          itemId,
          marketplaceId: mpId,
          listingTitle: itemName,
          price,
          currency,
          format,
          quantity: 1,
          conditionLabel: condition,
          status: 'draft',
          estimatedFees: fee?.totalFees ?? null,
          estimatedNet: fee?.netProceeds ?? null,
          feePercentage: fee ? Math.round(fee.totalFees / price * 100 * 10) / 10 : null,
        });
      }

      setVisible(false);
      return true;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create listings';
      setError(message);
      return false;
    } finally {
      setSubmitting(false);
    }
  }, [canSubmit, submitting, selectedIds, marketplaces, calculateFee, itemId, itemName, currency, format, condition]);

  return {
    // State
    visible,
    marketplaces,
    selectedIds,
    format,
    condition,
    feeBreakdowns,
    submitting,
    error,
    canSubmit,

    // Actions
    open,
    close,
    toggleMarketplace,
    setMarketplacePrice,
    setFormat,
    setCondition,
    submit,
    calculateFee,
  };
}
