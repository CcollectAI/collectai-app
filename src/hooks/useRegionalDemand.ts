/**
 * useRegionalDemand — the loader behind `RegionalInsightsSection`.
 *
 * Extracted from `app/market-hub.tsx` 2026-08-11 so the section could move to
 * the Market tab without its data staying behind. `RegionalInsightsSection`
 * returns null on an empty `items`, so a component moved WITHOUT this reads as
 * a working feature in the diff and renders nothing forever.
 *
 * A hook rather than a copied fetch: two copies of a cache key and a TTL drift,
 * and the copy that drifts is the one nobody is looking at.
 */
import { useEffect, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { collectorsApi } from '@/api/collectorsApi';
import logger from '@/utils/logger';

const REGIONAL_DEMAND_CACHE_KEY = '@regional_demand_cache';
const CACHE_TTL = 15 * 60 * 1000; // 15 minutes — same values the hub used.

export type RegionalDemandItem = {
  item_key: string;
  category: string;
  signal_count: number;
  region: string;
};

export function useRegionalDemand() {
  const [items, setItems] = useState<RegionalDemandItem[]>([]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const cached = await AsyncStorage.getItem(REGIONAL_DEMAND_CACHE_KEY);
        if (cached) {
          const { data, ts } = JSON.parse(cached);
          if (Date.now() - ts < CACHE_TTL) {
            if (!cancelled && Array.isArray(data)) setItems(data);
            return;
          }
        }
      } catch (e) {
        // Cache miss or unparseable entry — fall through to the network.
        // logger.error, not warn: warn is stripped from release builds.
        logger.error('[regionalDemand] cache read failed:', e);
      }

      try {
        const data = await collectorsApi.getDemandHeatByRegion();
        if (cancelled) return;
        const resp = data as { items?: RegionalDemandItem[] } | undefined;
        if (Array.isArray(resp?.items)) {
          const sliced = resp!.items.slice(0, 5);
          setItems(sliced);
          AsyncStorage.setItem(
            REGIONAL_DEMAND_CACHE_KEY,
            JSON.stringify({ data: sliced, ts: Date.now() }),
          ).catch(() => {});
        }
      } catch (err) {
        // Decoration on top of a grid: a failure must never block the screen.
        logger.error('[regionalDemand] getDemandHeatByRegion error:', err);
      }
    })();

    // `items` is NOT a dep — this effect sets it, and depending on what it
    // writes is the self-cancelling shape `check:effects` exists to catch.
    return () => {
      cancelled = true;
    };
  }, []);

  return { items };
}
