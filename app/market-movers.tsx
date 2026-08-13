/**
 * Market Movers — full "see all" screen for the biggest market price movers.
 *
 * Reached from the MarketMoversSection "See all" on the Marketplace tab. Adds
 * window (7d/30d), direction (gainers/losers) and scope (followed/all) toggles
 * on top of the same GET /catalog/top-movers feed. Rows deep-link to the catalog
 * museum detail. Read-only market data — no gating.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet, FlatList, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { Stack, useRouter, type Href } from 'expo-router';

import { useAppTheme } from '@/hooks/useAppTheme';
import { useBillingLimits } from '@/hooks/useBillingLimits';
import { UpgradePrompt } from '@/components/UpgradePrompt';
import { AnimatedPressable } from '@/motion';
import { collectorsApi } from '@/api/collectorsApi';
import type { TopMover } from '@/api/dataMoatApi';
import { useFollowedCategories } from '@/hooks/useFollowedCategories';
import { formatPrice } from '@/lib/format';
import { fireHaptic, HapticIntent } from '@/haptics';
import { radius, text, fontWeight } from '@/theme/tokens';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { moverKey, moverTitle } from '@/components/marketplace/MarketMoversSection';
import logger from '@/utils/logger';

type Direction = 'gainers' | 'losers';
type MetricWindow = '7d' | '30d';
type Scope = 'followed' | 'all';

/**
 * Secondary filter group — content-width, not full-bleed.
 *
 * The screen used to stack THREE identical full-width segmented controls
 * (direction, window, scope), ~150pt of chrome before the first row of data,
 * every one of them styled the same weight. Three equal controls read as three
 * equally important decisions; in fact only the first changes what the list
 * MEANS — gainers and losers are different questions — while window and scope
 * refine the same answer.
 *
 * So the primary keeps the full-width segmented treatment and these two shrink
 * to chips that sit together on one row. Same component API, so nothing about
 * the state wiring changed.
 */
function MiniSegmented<T extends string>(props: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.miniGroup, { borderColor: colors.border }]}>
      {props.options.map((o) => {
        const active = o.value === props.value;
        return (
          <AnimatedPressable
            key={o.value}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
              props.onChange(o.value);
            }}
            style={[styles.miniBtn, active && { backgroundColor: colors.accent + '1A' }]}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
          >
            <Text style={[styles.miniText, { color: active ? colors.accent : colors.muted }]}>
              {o.label}
            </Text>
          </AnimatedPressable>
        );
      })}
    </View>
  );
}

function Segmented<T extends string>(props: {
  options: { value: T; label: string; color?: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.segment, { borderColor: colors.border }]}>
      {props.options.map((o) => {
        const active = o.value === props.value;
        const c = o.color ?? colors.accent;
        return (
          <AnimatedPressable
            key={o.value}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
              props.onChange(o.value);
            }}
            style={[styles.segmentBtn, active && { backgroundColor: c + '1A' }]}
          >
            <Text style={[styles.segmentText, { color: active ? c : colors.muted }]}>{o.label}</Text>
          </AnimatedPressable>
        );
      })}
    </View>
  );
}

function MarketMoversScreen() {
  const { colors } = useAppTheme();
  const { limits } = useBillingLimits();
  const router = useRouter();
  const { followed } = useFollowedCategories();
  const [direction, setDirection] = useState<Direction>('gainers');
  const [metricWindow, setMetricWindow] = useState<MetricWindow>('7d');
  const [scope, setScope] = useState<Scope>('followed');
  const [movers, setMovers] = useState<TopMover[]>([]);
  const [loading, setLoading] = useState(true);
  // "Could not ask" is not "nothing to show". A failed fetch used to set
  // movers=[] and fall into the empty state, so the screen calmly reported
  // that the market had no movers — a claim it had no basis for. Retry nonce
  // rather than a state the effect reads, so the effect never depends on a
  // value it writes (npm run check:effects).
  const [failed, setFailed] = useState(false);
  const [retryNonce, setRetryNonce] = useState(0);

  const followedList = useMemo(() => Array.from(followed), [followed]);
  const hasFollowed = followedList.length > 0;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    const categories = scope === 'followed' && hasFollowed ? followedList : undefined;
    collectorsApi
      .getTopMovers({ direction, window: metricWindow, categories, limit: 50 })
      .then((res) => {
        if (!cancelled) setMovers(res?.movers ?? []);
      })
      .catch((err) => {
        // logger.error, not warn: warn is stripped in release builds, which is
        // exactly where a silently empty screen would be invisible.
        logger.error('[MarketMovers] fetch failed', err);
        if (!cancelled) {
          setMovers([]);
          setFailed(true);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [direction, metricWindow, scope, hasFollowed, followedList, retryNonce]);

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

  const renderItem = useCallback(
    ({ item: m }: { item: TopMover }) => {
      const delta = (metricWindow === '7d' ? m.delta_pct_7d : m.delta_pct_30d) ?? 0;
      const up = delta >= 0;
      const c = up ? colors.success : colors.danger;
      return (
        <AnimatedPressable onPress={() => openItem(m)} style={[styles.row, { borderBottomColor: colors.border }]}>
          {m.image_url ? (
            <Image source={{ uri: m.image_url }} style={styles.thumb} contentFit="contain" transition={120} />
          ) : (
            <View style={[styles.thumb, styles.thumbPlaceholder, { backgroundColor: colors.border }]}>
              <Ionicons name="pricetag-outline" size={18} color={colors.muted} />
            </View>
          )}
          <View style={styles.rowText}>
            <Text style={[styles.name, { color: colors.text }]} numberOfLines={1}>
              {moverTitle(m)}
            </Text>
            <Text style={[styles.sub, { color: colors.muted }]} numberOfLines={1}>
              {m.category} · {formatPrice(m.last_price)} · {m.comps_30d} comps
            </Text>
          </View>
          <Text style={[styles.delta, { color: c }]}>
            {up ? '+' : ''}
            {delta.toFixed(1)}%
          </Text>
        </AnimatedPressable>
      );
    },
    [metricWindow, colors, openItem],
  );

  // The section on the Market tab shows a locked preview to non-Pro members,
  // and its "See all" sends them to /settings instead of here. This is the
  // second lock, for the route itself: a paywall that only exists on the
  // control that opens a screen is one deep link from being no paywall at all.
  if (!limits.advanced_analytics) {
    return (
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <Stack.Screen
          options={{
            headerTitle: 'Market Movers',
            headerTintColor: colors.text,
            headerStyle: { backgroundColor: colors.background },
          }}
        />
        <UpgradePrompt feature="Market Movers" requiredPlan="Pro" />
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <Stack.Screen
        options={{
          headerTitle: 'Market Movers',
          headerTintColor: colors.text,
          headerStyle: { backgroundColor: colors.background },
        }}
      />

      <View style={styles.controls}>
        {/* Primary: gainers and losers are different questions, not a refinement. */}
        <Segmented<Direction>
          value={direction}
          onChange={setDirection}
          options={[
            { value: 'gainers', label: 'Gainers', color: colors.success },
            { value: 'losers', label: 'Losers', color: colors.danger },
          ]}
        />
        {/* Secondary: both refine the same answer, so they share one row and
            size to their own content instead of each claiming a full bar. */}
        <View style={styles.filterRow}>
          <MiniSegmented<MetricWindow>
            value={metricWindow}
            onChange={setMetricWindow}
            options={[
              { value: '7d', label: '7 days' },
              { value: '30d', label: '30 days' },
            ]}
          />
          {hasFollowed && (
            <MiniSegmented<Scope>
              value={scope}
              onChange={setScope}
              options={[
                { value: 'followed', label: 'My categories' },
                { value: 'all', label: 'All' },
              ]}
            />
          )}
        </View>
      </View>

      {loading ? (
        <ActivityIndicator style={styles.loader} size="large" color={colors.accent} />
      ) : failed ? (
        <View style={styles.empty}>
          <Ionicons name="cloud-offline-outline" size={40} color={colors.muted} />
          <Text style={[styles.emptyText, { color: colors.muted }]}>
            Couldn&apos;t load market movers.
          </Text>
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
              setRetryNonce((n) => n + 1);
            }}
            style={[styles.retryBtn, { backgroundColor: colors.accent }]}
            accessibilityRole="button"
            accessibilityLabel="Try loading market movers again"
          >
            <Text style={[styles.retryText, { color: colors.accentText }]}>Try again</Text>
          </AnimatedPressable>
        </View>
      ) : movers.length === 0 ? (
        <View style={styles.empty}>
          <Ionicons name="trending-up-outline" size={40} color={colors.muted} />
          <Text style={[styles.emptyText, { color: colors.muted }]}>No movers to show right now.</Text>
        </View>
      ) : (
        <FlatList
          data={movers}
          keyExtractor={(m) => m.item_ref}
          renderItem={renderItem}
          contentContainerStyle={styles.list}
        />
      )}
    </View>
  );
}

export default function MarketMoversScreenWrapper() {
  return (
    <ScreenErrorBoundary>
      <MarketMoversScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  controls: {
    gap: 10,
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 10,
  },
  segment: {
    flexDirection: 'row',
    borderWidth: 1,
    borderRadius: radius.pill,
    padding: 3,
  },
  segmentBtn: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 7,
    borderRadius: radius.pill,
  },
  segmentText: {
    // `md`, not `sm`: this is the screen's primary control and the playbook's
    // floor for anything a user reads is 12 — a 12pt primary control next to
    // 12pt secondary chips is why all three bars read as one undifferentiated
    // block.
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  // Secondary filters share one row and size to content.
  filterRow: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
  },
  miniGroup: {
    flexDirection: 'row',
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.pill,
    padding: 2,
  },
  // No `flex: 1` — that is the whole difference from `segmentBtn`. These size
  // to their labels so two groups fit one row.
  miniBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.pill,
  },
  miniText: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
  },
  retryBtn: {
    marginTop: 14,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: radius.md,
  },
  retryText: { fontSize: text.md, fontWeight: fontWeight.bold },
  loader: {
    marginTop: 40,
  },
  empty: {
    alignItems: 'center',
    marginTop: 60,
    gap: 12,
  },
  emptyText: {
    fontSize: text.md,
  },
  list: {
    paddingHorizontal: 16,
    paddingBottom: 32,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    gap: 12,
  },
  thumb: {
    width: 44,
    height: 44,
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
    fontSize: text.lg,
    fontWeight: fontWeight.bold,
  },
});
