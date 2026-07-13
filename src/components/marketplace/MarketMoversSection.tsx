/**
 * MarketMoversSection — compact "Market Movers" widget for the Marketplace tab.
 *
 * Shows the biggest 7d price gainers/losers across the market, defaulting to the
 * user's followed categories (falls back to whole-catalog when none are
 * followed). Data comes from the `mv_market_top_movers` MV via
 * GET /catalog/top-movers. Rows deep-link to the catalog museum detail; "See all"
 * opens the full /market-movers screen. Self-fetching so the tab only renders
 * one line. Hides itself when there is nothing to show.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { useRouter, type Href } from 'expo-router';

import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { collectorsApi } from '@/api/collectorsApi';
import type { TopMover } from '@/api/dataMoatApi';
import { useFollowedCategories } from '@/hooks/useFollowedCategories';
import { formatPrice } from '@/lib/format';
import { fireHaptic, HapticIntent } from '@/haptics';
import { radius, text, fontWeight } from '@/theme/tokens';
import logger from '@/utils/logger';

type Direction = 'gainers' | 'losers';

/** Catalog item_key for deep-linking (strip the `category:` prefix when unmatched). */
export function moverKey(m: TopMover): string {
  return m.item_key ?? m.item_ref.split(':').slice(1).join(':');
}
/** Display name — catalog title, or the derived key when the item isn't in the catalog. */
export function moverTitle(m: TopMover): string {
  return m.title ?? moverKey(m);
}

function MarketMoversSectionInner() {
  const { colors } = useAppTheme();
  const router = useRouter();
  const { followed } = useFollowedCategories();
  const [direction, setDirection] = useState<Direction>('gainers');
  const [movers, setMovers] = useState<TopMover[]>([]);
  const [loading, setLoading] = useState(true);

  const categories = useMemo(() => Array.from(followed), [followed]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    collectorsApi
      .getTopMovers({ direction, window: '7d', categories, limit: 5 })
      .then((res) => {
        if (!cancelled) setMovers(res?.movers ?? []);
      })
      .catch((err) => {
        logger.warn('[MarketMovers] fetch failed', err);
        if (!cancelled) setMovers([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [direction, categories]);

  const openItem = useCallback(
    (m: TopMover) => {
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
      router.push({
        pathname: '/catalog-item/[key]',
        params: {
          key: moverKey(m),
          category: m.category,
          title: moverTitle(m),
          image_url: m.image_url ?? '',
          set_code: m.set_code ?? '',
          brand: m.brand ?? '',
          estimated_price: m.last_price != null ? String(m.last_price) : '',
        },
      } as unknown as Href);
    },
    [router],
  );

  // Hide the whole card when there's nothing to show (never render an empty shell).
  if (!loading && movers.length === 0) return null;

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Text style={[styles.title, { color: colors.text }]}>Market Movers</Text>
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
            router.push('/market-movers' as Href);
          }}
          hitSlop={8}
        >
          <Text style={[styles.seeAll, { color: colors.success }]}>See all</Text>
        </AnimatedPressable>
      </View>

      <View style={styles.toggleRow}>
        {(['gainers', 'losers'] as Direction[]).map((d) => {
          const active = d === direction;
          const c = d === 'gainers' ? colors.success : colors.danger;
          return (
            <AnimatedPressable
              key={d}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                setDirection(d);
              }}
              style={[
                styles.chip,
                { borderColor: active ? c : colors.border, backgroundColor: active ? c + '1A' : 'transparent' },
              ]}
            >
              <Ionicons
                name={d === 'gainers' ? 'trending-up' : 'trending-down'}
                size={14}
                color={active ? c : colors.muted}
              />
              <Text style={[styles.chipText, { color: active ? c : colors.muted }]}>
                {d === 'gainers' ? 'Gainers' : 'Losers'}
              </Text>
            </AnimatedPressable>
          );
        })}
        <Text style={[styles.window, { color: colors.muted }]}>7d change</Text>
      </View>

      {loading ? (
        <ActivityIndicator style={styles.loader} color={colors.muted} />
      ) : (
        movers.map((m) => {
          const delta = m.delta_pct_7d ?? 0;
          const up = delta >= 0;
          const c = up ? colors.success : colors.danger;
          return (
            <AnimatedPressable
              key={m.item_ref}
              onPress={() => openItem(m)}
              style={[styles.row, { borderBottomColor: colors.border }]}
            >
              {m.image_url ? (
                <Image source={{ uri: m.image_url }} style={styles.thumb} contentFit="contain" transition={120} />
              ) : (
                <View style={[styles.thumb, styles.thumbPlaceholder, { backgroundColor: colors.border }]}>
                  <Ionicons name="pricetag-outline" size={16} color={colors.muted} />
                </View>
              )}
              <View style={styles.rowText}>
                <Text style={[styles.name, { color: colors.text }]} numberOfLines={1}>
                  {moverTitle(m)}
                </Text>
                <Text style={[styles.sub, { color: colors.muted }]} numberOfLines={1}>
                  {m.category} · {formatPrice(m.last_price)}
                </Text>
              </View>
              <Text style={[styles.delta, { color: c }]}>
                {up ? '+' : ''}
                {delta.toFixed(1)}%
              </Text>
            </AnimatedPressable>
          );
        })
      )}
    </View>
  );
}

export const MarketMoversSection = React.memo(MarketMoversSectionInner);

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  title: {
    fontSize: text.lg,
    fontWeight: fontWeight.bold,
  },
  seeAll: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: radius.pill,
    borderWidth: 1,
  },
  chipText: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
  },
  window: {
    marginLeft: 'auto',
    fontSize: text.sm,
  },
  loader: {
    marginVertical: 16,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    gap: 12,
  },
  thumb: {
    width: 36,
    height: 36,
    borderRadius: radius.sm,
  },
  thumbPlaceholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowText: {
    flex: 1,
  },
  name: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  sub: {
    fontSize: text.sm,
    marginTop: 2,
  },
  delta: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
  },
});
