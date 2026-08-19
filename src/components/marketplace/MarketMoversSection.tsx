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
import { useBillingLimits } from '@/hooks/useBillingLimits';
import { formatPrice } from '@/lib/format';
import { fireHaptic, HapticIntent } from '@/haptics';
import { radius, text, fontWeight } from '@/theme/tokens';
import logger from '@/utils/logger';

type Direction = 'gainers' | 'losers';

// Display helpers live in ./moverFormat (pure, no hooks) so tests can import
// them without dragging this component's dependency graph — including the
// RevenueCat SDK behind useBillingLimits — into a jest module registry that
// cannot parse it.
export { moverKey, moverTitle, humaniseMoverKey } from './moverFormat';
import { moverKey, moverTitle, PCT_MIN_PRICE_EUR } from './moverFormat';
import { formatCategoryName } from '@/constants/categories';

function MarketMoversSectionInner() {
  const { colors } = useAppTheme();
  // Same key app/analytics.tsx gates every Pro section on, so movers cannot
  // drift out of step with the rest of the paywall.
  const { limits } = useBillingLimits();
  const locked = !limits.advanced_analytics;
  const router = useRouter();
  const { followed } = useFollowedCategories();
  const [direction, setDirection] = useState<Direction>('gainers');
  const [movers, setMovers] = useState<TopMover[]>([]);
  const [loading, setLoading] = useState(true);

  const categories = useMemo(() => Array.from(followed), [followed]);

  useEffect(() => {
    // Locked members never fetch. The preview below is drawn from nothing, so
    // the paid figures are not sitting in memory (or in a network log) on a
    // device that has not paid for them — and the tab makes one less request.
    if (locked) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    collectorsApi
      .getTopMovers({
        direction,
        window: '7d',
        categories,
        limit: 5,
        // Same floor as the full screen (moverFormat), so the widget and the
        // screen behind its "See all" answer the same question.
        minPriceEur: PCT_MIN_PRICE_EUR,
      })
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
  }, [direction, categories, locked]);

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

  // Hide the whole card when there's nothing to show (never render an empty
  // shell) — but NOT when locked, where having no rows is the point.
  if (!locked && !loading && movers.length === 0) return null;

  if (locked) {
    return (
      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.header}>
          <Text style={[styles.title, { color: colors.text }]}>Market Movers</Text>
          <View style={[styles.proPill, { backgroundColor: colors.accent + '1E' }]}>
            <Ionicons name="lock-closed" size={11} color={colors.accent} />
            <Text style={[styles.proPillText, { color: colors.accent }]}>PRO</Text>
          </View>
        </View>

        <Text style={[styles.lockedBlurb, { color: colors.muted }]}>
          The biggest 7-day price moves across your categories — what is climbing,
          what is falling, and by how much.
        </Text>

        {/* Three masked rows. The SHAPE of the feature is the pitch; the
            numbers are the product. Grey bars rather than blurred real data,
            because a blur is a rendering trick over values that were still
            fetched and can still be read off the wire. */}
        {[0, 1, 2].map((i) => (
          <View key={i} style={[styles.row, { borderBottomColor: colors.border }]}>
            <View style={[styles.thumb, styles.thumbPlaceholder, { backgroundColor: colors.border }]}>
              <Ionicons name="pricetag-outline" size={16} color={colors.muted} />
            </View>
            <View style={styles.lockedTextCol}>
              <View style={[styles.lockedBar, { backgroundColor: colors.border, width: `${72 - i * 12}%` }]} />
              <View style={[styles.lockedBarSm, { backgroundColor: colors.border, width: `${44 - i * 8}%` }]} />
            </View>
            <View style={[styles.lockedDelta, { backgroundColor: colors.border }]} />
          </View>
        ))}

        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
            // Paywall, not Settings — same defect as UpgradePrompt.tsx, fixed
            // 2026-08-15. Swept for with the accessibilityLabel/onPress pair.
            router.push('/subscription' as Href);
          }}
          style={[styles.upgradeBtn, { backgroundColor: colors.accent }]}
          accessibilityRole="button"
          accessibilityLabel="Upgrade to Pro to see Market Movers"
        >
          <Text style={[styles.upgradeBtnText, { color: colors.accentText }]}>
            Upgrade to see
          </Text>
        </AnimatedPressable>
      </View>
    );
  }

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <View style={styles.titleWrap}>
          <Text style={[styles.title, { color: colors.text }]}>Market Movers</Text>
          {/* The window belongs to the heading, not to a label floating at the
              end of the filter row. Same information, one less thing to scan. */}
          <Text style={[styles.window, { color: colors.muted }]}>7d</Text>
        </View>
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
      </View>

      {loading ? (
        <ActivityIndicator style={styles.loader} color={colors.muted} />
      ) : (
        movers.map((m, idx) => {
          const delta = m.delta_pct_7d ?? 0;
          // Server-computed from the same columns as the percentage — never
          // recomputed here (see TopMover.delta_eur_*).
          const deltaEur = m.delta_eur_7d;
          const up = delta >= 0;
          const c = up ? colors.success : colors.danger;
          return (
            <AnimatedPressable
              key={m.item_ref}
              onPress={() => openItem(m)}
              style={[
                styles.row,
                // No hairline under the last row: it would sit directly above
                // the card's own bottom padding, drawing a line to nothing.
                idx === movers.length - 1
                  ? styles.rowLast
                  : { borderBottomColor: colors.border },
              ]}
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
                  {formatCategoryName(m.category)} · {formatPrice(m.last_price)}
                </Text>
              </View>
              {/* Percentage leads, money qualifies it: "+96.7%" alone hides
                  that the move was EUR 1.77. */}
              <View style={styles.deltaCol}>
                <Text style={[styles.delta, { color: c }]}>
                  {up ? '+' : ''}
                  {delta.toFixed(1)}%
                </Text>
                {typeof deltaEur === 'number' ? (
                  <Text style={[styles.deltaSub, { color: c }]}>
                    {deltaEur >= 0 ? '+' : '−'}
                    {formatPrice(Math.abs(deltaEur))}
                  </Text>
                ) : null}
              </View>
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
    padding: 12,
    marginBottom: 12,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  titleWrap: { flexDirection: 'row', alignItems: 'baseline', gap: 6 },
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
    marginBottom: 4,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: radius.pill,
    borderWidth: 1,
  },
  chipText: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
  },
  window: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
  },
  loader: {
    marginVertical: 16,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 7,
    borderBottomWidth: 1,
    gap: 10,
  },
  // Keeps the row's height identical to its neighbours — setting borderWidth to
  // 0 instead would make the last row 1pt shorter than the rest.
  rowLast: { borderBottomColor: 'transparent' },
  thumb: {
    width: 32,
    height: 32,
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
    marginTop: 1,
  },
  // ── Locked (non-Pro) preview ──────────────────────────────────────────
  proPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.pill,
  },
  proPillText: { fontSize: text.sm, fontWeight: fontWeight.extrabold, letterSpacing: 0.4 },
  lockedBlurb: { fontSize: text.md, lineHeight: 19, marginBottom: 8 },
  lockedTextCol: { flex: 1, gap: 6, marginLeft: 10 },
  // Masked values. Rounded bars read as "content withheld"; a blur would read
  // as a rendering fault, and would also mean the real numbers were fetched.
  lockedBar: { height: 10, borderRadius: 5 },
  lockedBarSm: { height: 8, borderRadius: 4 },
  lockedDelta: { width: 52, height: 12, borderRadius: 6 },
  upgradeBtn: {
    marginTop: 10, borderRadius: radius.md,
    paddingVertical: 10, alignItems: 'center',
  },
  upgradeBtnText: { fontSize: text.md, fontWeight: fontWeight.bold },
  deltaCol: { alignItems: 'flex-end', minWidth: 76 },
  delta: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
  },
  // Qualifies the percentage above it — same colour, one step down.
  deltaSub: { fontSize: text.sm, fontWeight: fontWeight.semibold, marginTop: 1 },
});
