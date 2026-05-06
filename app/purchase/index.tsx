/**
 * Agent Hub — Smart Deal Agent main screen.
 *
 * Shows active mandates as cards, recent deals feed, and create mandate button.
 */

import React, { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Linking,
  RefreshControl,
  Platform,
  Image,
  Animated,
  Easing,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useAppTheme } from "@/hooks/useAppTheme";
import { useSettings } from "@/lib/settings";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { formatPrice } from "@/lib/format";
import { collectorsApi } from "@/api/collectorsApi";
import { QuickNavBar } from "@/components/QuickNavBar";
import type { PurchaseMandate, MandateDeal } from "@/data/types";

const DEALS_PAGE_SIZE = 10;

/** Map a mandate's category slug to a Sparrow-recognizable icon. */
function categoryIcon(category?: string | null): keyof typeof Ionicons.glyphMap {
  if (!category) return 'pricetag-outline';
  const c = category.toLowerCase();
  if (c.includes('pokemon') || c.includes('mtg') || c.includes('yugioh') ||
      c.includes('lorcana') || c.includes('one_piece') || c.includes('sportscards') ||
      c.includes('card')) return 'albums-outline';
  if (c.includes('lego')) return 'cube-outline';
  if (c.includes('funko') || c.includes('hot_toys') || c.includes('figure') ||
      c.includes('vtuber') || c.includes('disney') || c.includes('ghibli')) return 'happy-outline';
  if (c.includes('vinyl') || c.includes('soundtrack') || c.includes('music')) return 'disc-outline';
  if (c.includes('watch')) return 'time-outline';
  if (c.includes('sneaker')) return 'walk-outline';
  if (c.includes('manga') || c.includes('comic') || c.includes('book')) return 'book-outline';
  if (c.includes('camera')) return 'camera-outline';
  if (c.includes('warhammer') || c.includes('gunpla') || c.includes('scale')) return 'construct-outline';
  if (c.includes('retro_games') || c.includes('nintendo')) return 'game-controller-outline';
  if (c.includes('kpop') || c.includes('taylor_swift')) return 'musical-notes-outline';
  if (c.includes('keycaps') || c.includes('pen')) return 'create-outline';
  if (c.includes('whiskey')) return 'wine-outline';
  if (c.includes('fragrance')) return 'flower-outline';
  return 'pricetag-outline';
}

/** Format relative time as "Just now", "4 min ago", "2 hours ago", "yesterday". */
function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return "Just now";
  const min = Math.floor(ms / 60_000);
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} ${hr === 1 ? "hour" : "hours"} ago`;
  const d = Math.floor(hr / 24);
  if (d === 1) return "yesterday";
  if (d < 7) return `${d} days ago`;
  return new Date(iso).toLocaleDateString();
}

export default function AgentHubScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Smart Deal Agent">
      <AgentHubScreen />
    </ScreenErrorBoundary>
  );
}

function AgentHubScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  const [mandates, setMandates] = useState<PurchaseMandate[]>([]);
  const [deals, setDeals] = useState<MandateDeal[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMoreDeals, setHasMoreDeals] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Force re-render once a minute so the "Last scan: X min ago" label
  // stays current without remounting the screen.
  const [, setNowTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setNowTick((n) => n + 1), 60_000);
    return () => clearInterval(t);
  }, []);

  // Three concentric pulse rings — staggered to feel like a radar sweep
  // instead of a single notification dot. Each ring runs the same loop
  // but starts ~450ms after the previous, so at any given frame three
  // rings are at different scales/opacities. All native-driver.
  const pulseAnim1 = useRef(new Animated.Value(0)).current;
  const pulseAnim2 = useRef(new Animated.Value(0)).current;
  const pulseAnim3 = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const makeLoop = (a: Animated.Value, delay: number) => {
      a.setValue(0);
      return Animated.loop(
        Animated.sequence([
          Animated.delay(delay),
          Animated.timing(a, {
            toValue: 1,
            duration: 1500,
            easing: Easing.out(Easing.quad),
            useNativeDriver: true,
          }),
          Animated.timing(a, {
            toValue: 0,
            duration: 0,
            useNativeDriver: true,
          }),
        ]),
      );
    };
    const loops = [makeLoop(pulseAnim1, 0), makeLoop(pulseAnim2, 500), makeLoop(pulseAnim3, 1000)];
    loops.forEach((l) => l.start());
    return () => loops.forEach((l) => l.stop());
  }, [pulseAnim1, pulseAnim2, pulseAnim3]);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      setHasMoreDeals(true);
      const [mandateRes, dealRes] = await Promise.all([
        collectorsApi.listMandates(20, 0),
        collectorsApi.listDeals({ limit: DEALS_PAGE_SIZE, offset: 0 }),
      ]);
      const mandateData = mandateRes as { mandates?: typeof mandates } | undefined;
      const dealData = dealRes as { deals?: typeof deals } | undefined;
      setMandates(mandateData?.mandates ?? []);
      const initialDeals = dealData?.deals ?? [];
      setDeals(initialDeals);
      if (initialDeals.length < DEALS_PAGE_SIZE) setHasMoreDeals(false);
    } catch {
      setError('Could not load deals. Pull to refresh.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadData();
  }, [loadData]);

  const loadMoreDeals = useCallback(async () => {
    if (loadingMore || !hasMoreDeals) return;
    setLoadingMore(true);
    try {
      const res = await collectorsApi.listDeals({
        limit: DEALS_PAGE_SIZE,
        offset: deals.length,
      });
      const data = res as { deals?: MandateDeal[] } | undefined;
      const newDeals = data?.deals ?? [];
      setDeals((prev) => [...prev, ...newDeals]);
      if (newDeals.length < DEALS_PAGE_SIZE) setHasMoreDeals(false);
    } catch {
      setError('Could not load more deals.');
    } finally {
      setLoadingMore(false);
    }
  }, [deals.length, hasMoreDeals, loadingMore]);

  // Most-recent scan timestamp across all active mandates.
  const lastScanLabel = useMemo(() => {
    const stamps = mandates
      .filter((m) => m.lastScanAt)
      .map((m) => new Date(m.lastScanAt!).getTime());
    if (!stamps.length) return null;
    return formatRelativeTime(new Date(Math.max(...stamps)).toISOString());
  }, [mandates]);

  const activeMandateCount = mandates.filter((m) => m.status === 'active').length;

  const statusColor = (status: string) => {
    switch (status) {
      case "active": return colors.success;
      case "paused": return colors.warning;
      default: return colors.muted;
    }
  };

  const dealStatusBadge = (status: string) => {
    const map: Record<string, { label: string; color: string }> = {
      discovered: { label: "New", color: colors.accent },
      notified: { label: "Sent", color: colors.info },
      clicked: { label: "Viewed", color: colors.warning },
      purchased: { label: "Bought", color: colors.success },
      declined: { label: "Skipped", color: colors.muted },
      expired: { label: "Expired", color: colors.danger },
    };
    return map[status] ?? { label: status, color: colors.muted };
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={["left", "right"]}>
        <View style={[styles.container, { paddingTop: 12 }]}>
          {/* Header skeleton */}
          <View style={[styles.skeletonHeader, { backgroundColor: colors.card }]} />
          {/* Scan-status row skeleton */}
          <View style={[styles.skeletonScan, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={[styles.skeletonDot, { backgroundColor: colors.border }]} />
            <View style={{ flex: 1, gap: 6 }}>
              <View style={[styles.skeletonLine, { backgroundColor: colors.border, width: '60%' }]} />
              <View style={[styles.skeletonLine, { backgroundColor: colors.border, width: '40%', height: 10 }]} />
            </View>
          </View>
          {/* Mandate card skeletons */}
          {[0, 1].map((i) => (
            <View key={i} style={[styles.skeletonCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <View style={[styles.skeletonIconSquare, { backgroundColor: colors.border }]} />
                <View style={[styles.skeletonLine, { backgroundColor: colors.border, flex: 1 }]} />
              </View>
              <View style={[styles.skeletonLine, { backgroundColor: colors.border, width: '70%', marginBottom: 14 }]} />
              <View style={{ flexDirection: 'row', gap: 16 }}>
                <View style={[styles.skeletonLine, { backgroundColor: colors.border, width: 80 }]} />
                <View style={[styles.skeletonLine, { backgroundColor: colors.border, width: 80 }]} />
              </View>
            </View>
          ))}
          {/* Deal row skeletons (with thumbnail block on left) */}
          <View style={[styles.skeletonCard, { backgroundColor: colors.card, borderColor: colors.border, padding: 0 }]}>
            {[0, 1, 2].map((i) => (
              <View key={i} style={[styles.skeletonDealRow, i > 0 && { borderTopWidth: 1, borderTopColor: colors.border }]}>
                <View style={[styles.skeletonThumb, { backgroundColor: colors.border }]} />
                <View style={{ flex: 1, gap: 6 }}>
                  <View style={[styles.skeletonLine, { backgroundColor: colors.border, width: '85%' }]} />
                  <View style={[styles.skeletonLine, { backgroundColor: colors.border, width: '50%', height: 10 }]} />
                </View>
                <View style={[styles.skeletonLine, { backgroundColor: colors.border, width: 50 }]} />
              </View>
            ))}
          </View>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={["left", "right"]}>
      {error && (
        <View style={{ backgroundColor: colors.danger + '10', padding: 12, borderRadius: 8, marginHorizontal: 16, marginBottom: 8, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Ionicons name="warning-outline" size={14} color={colors.danger} />
          <Text style={{ color: colors.danger, fontSize: 13, flex: 1 }}>{error}</Text>
        </View>
      )}
      <ScrollView
        contentContainerStyle={styles.container}
        showsVerticalScrollIndicator={false}
        // Index 1 = scan-status row. Stays pinned to the top while the
        // user scrolls deals, so the "watching X things, last scan Y"
        // context never disappears.
        stickyHeaderIndices={(activeMandateCount > 0 || lastScanLabel) ? [1] : undefined}
        // Trigger Load More when scrolled near the bottom (within 200px),
        // gives infinite-scroll feel; the explicit Load More button below
        // is kept as fallback for users who want to control fetches.
        onScroll={(e) => {
          const { layoutMeasurement, contentOffset, contentSize } = e.nativeEvent;
          const distanceFromBottom = contentSize.height - (contentOffset.y + layoutMeasurement.height);
          if (distanceFromBottom < 200 && hasMoreDeals && !loadingMore && deals.length >= DEALS_PAGE_SIZE) {
            loadMoreDeals();
          }
        }}
        scrollEventThrottle={250}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
        }
      >
        {/* Header — index 0 */}
        <View style={styles.headerRow}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.headerTitle, { color: colors.text }]}>Sparrow's Watch</Text>
            <Text style={[styles.headerSubtitle, { color: colors.muted }]}>
              A little bird watching the marketplaces for you.
            </Text>
          </View>
          <AnimatedPressable
            style={[styles.createBtn, { backgroundColor: colors.accent }]}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              router.push("/purchase/create-mandate");
            }}
            accessibilityRole="button"
            accessibilityLabel="Tell Sparrow what to watch"
          >
            <Ionicons name="add" size={20} color="#fff" />
            <Text style={styles.createBtnText}>Watch</Text>
          </AnimatedPressable>
        </View>

        {/* Live status — index 1 (sticky). Wrapped in opaque background so
            content scrolling under it doesn't bleed through. */}
        {(activeMandateCount > 0 || lastScanLabel) && (
          <View
            style={[styles.scanStatus, { backgroundColor: colors.card, borderColor: colors.border }]}
            accessibilityRole="text"
            accessibilityLabel={`Sparrow is watching ${activeMandateCount} ${activeMandateCount === 1 ? 'thing' : 'things'}, last scan ${lastScanLabel ?? 'pending'}`}
          >
            <View style={styles.pulseWrap}>
              {[pulseAnim1, pulseAnim2, pulseAnim3].map((anim, i) => (
                <Animated.View
                  key={i}
                  style={[
                    styles.pulseRing,
                    {
                      borderColor: colors.accent,
                      transform: [
                        {
                          scale: anim.interpolate({ inputRange: [0, 1], outputRange: [0.8, 2.6] }),
                        },
                      ],
                      opacity: anim.interpolate({ inputRange: [0, 0.1, 1], outputRange: [0, 0.55, 0] }),
                    },
                  ]}
                />
              ))}
              <View style={[styles.pulseDot, { backgroundColor: colors.accent }]} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.scanStatusTitle, { color: colors.text }]}>
                {activeMandateCount > 0
                  ? `Watching ${activeMandateCount} ${activeMandateCount === 1 ? 'thing' : 'things'} for you`
                  : 'Idle'}
              </Text>
              <Text style={[styles.scanStatusSub, { color: colors.muted }]} numberOfLines={1}>
                {lastScanLabel ? `Last scan ${lastScanLabel}` : 'Sparrow will start watching shortly.'}
              </Text>
            </View>
          </View>
        )}

        {/* Active Mandates */}
        <Text style={[styles.sectionTitle, { color: colors.text }]}>What Sparrow's watching</Text>

        {mandates.length === 0 ? (
          <View style={[styles.emptyCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Ionicons name="search-outline" size={32} color={colors.muted} />
            <Text style={[styles.emptyTitle, { color: colors.text }]}>Sparrow hasn't started watching yet</Text>
            <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
              Tell Sparrow what you're hunting and the price you'd pay. You'll hear a chirp the moment something matches.
            </Text>
            <View style={styles.emptyCtaContainer}>
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  router.push("/purchase/create-mandate");
                }}
                style={[styles.emptyCtaBtn, { backgroundColor: colors.accent }]}
                accessibilityRole="button"
                accessibilityLabel="Tell Sparrow what to watch"
              >
                <Text style={styles.emptyCtaBtnText}>Tell Sparrow what to watch</Text>
              </AnimatedPressable>
            </View>
          </View>
        ) : (
          mandates.map((m) => {
            const budgetPct = m.maxTotalBudget
              ? Math.min(1, m.spentTotal / m.maxTotalBudget)
              : 0;
            const budgetColor = budgetPct > 0.8 ? colors.warning : colors.accent;

            return (
              <AnimatedPressable
                key={m.id}
                style={[styles.mandateCard, { backgroundColor: colors.card, borderColor: colors.border }]}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  router.push(`/purchase/create-mandate?id=${m.id}`);
                }}
                accessibilityRole="button"
                accessibilityLabel={`Watching: ${m.name}, ${m.dealsFound} spotted, cap ${formatPrice(m.maxPrice)}`}
              >
                <View style={styles.mandateHeader}>
                  {/* Category-aware icon prefix — visually differentiates mandate types
                      in a long list (Pokemon → albums, LEGO → cube, watches → clock). */}
                  <View style={[styles.mandateCategoryIcon, { backgroundColor: colors.accent + '15' }]}>
                    <Ionicons name={categoryIcon(m.category)} size={16} color={colors.accent} />
                  </View>
                  <Text style={[styles.mandateName, { color: colors.text }]} numberOfLines={1}>
                    {m.name}
                  </Text>
                  <View style={[styles.statusBadge, { backgroundColor: statusColor(m.status) + "20" }]}>
                    <Text style={[styles.statusText, { color: statusColor(m.status) }]}>
                      {m.status}
                    </Text>
                  </View>
                </View>

                <Text style={[styles.mandateQuery, { color: colors.muted }]} numberOfLines={1}>
                  {m.searchQuery}
                </Text>

                {/* Two stats with icons — Spotted (deals found) + Cap (max price per match) */}
                <View style={styles.mandateStats}>
                  <View style={styles.statBlock}>
                    <View style={[styles.statIcon, { backgroundColor: colors.accent + "18" }]}>
                      <Ionicons name="eye-outline" size={14} color={colors.accent} />
                    </View>
                    <View>
                      <Text style={[styles.statValue, { color: colors.text }]}>{m.dealsFound}</Text>
                      <Text style={[styles.statLabel, { color: colors.muted }]}>spotted</Text>
                    </View>
                  </View>
                  <View style={styles.statBlock}>
                    <View style={[styles.statIcon, { backgroundColor: colors.muted + "18" }]}>
                      <Ionicons name="pricetag-outline" size={14} color={colors.muted} />
                    </View>
                    <View>
                      <Text style={[styles.statValue, { color: colors.text }]}>
                        {formatPrice(m.maxPrice)}
                      </Text>
                      <Text style={[styles.statLabel, { color: colors.muted }]}>cap per match</Text>
                    </View>
                  </View>
                </View>

                {m.maxTotalBudget != null && (
                  <View style={styles.budgetBar}>
                    <View style={[styles.budgetTrack, { backgroundColor: colors.border }]}>
                      <View
                        style={[
                          styles.budgetFill,
                          { backgroundColor: budgetColor, width: `${budgetPct * 100}%` },
                        ]}
                      />
                    </View>
                    <View style={styles.budgetTextRow}>
                      <Text style={[styles.budgetText, { color: colors.muted }]}>
                        {formatPrice(m.spentTotal)} of {formatPrice(m.maxTotalBudget)} budget
                      </Text>
                      <Text style={[styles.budgetText, { color: budgetColor, fontWeight: "700" }]}>
                        {Math.round(budgetPct * 100)}%
                      </Text>
                    </View>
                  </View>
                )}
              </AnimatedPressable>
            );
          })
        )}

        {/* Recent Deals */}
        <Text style={[styles.sectionTitle, { color: colors.text, marginTop: 24 }]}>What Sparrow spotted</Text>

        {deals.length === 0 ? (
          <View style={[styles.emptyCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Ionicons name="pricetag-outline" size={32} color={colors.muted} />
            <Text style={[styles.emptyTitle, { color: colors.text }]}>Nothing spotted yet</Text>
            <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
              Sparrow will leave deals here as it spots them.
            </Text>
          </View>
        ) : (
          <View style={[styles.dealsCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            {deals.map((deal, idx) => {
              const badge = dealStatusBadge(deal.status);
              return (
                <AnimatedPressable
                  key={deal.id}
                  style={[
                    styles.dealRow,
                    { borderTopColor: colors.border },
                    idx === 0 && styles.dealRowFirst,
                  ]}
                  onPress={() => {
                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                    router.push(`/purchase/deal/${deal.id}`);
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={`Deal: ${deal.listingTitle}, ${formatPrice(deal.listingPrice)}`}
                >
                  {/* Thumbnail — shows the actual listing image when available;
                      falls back to a category-tinted placeholder so rows always
                      have visual anchor. */}
                  {deal.listingImageUrl ? (
                    <Image
                      source={{ uri: deal.listingImageUrl }}
                      style={[styles.dealThumb, { backgroundColor: colors.border }]}
                      accessibilityIgnoresInvertColors
                    />
                  ) : (
                    <View style={[styles.dealThumb, styles.dealThumbFallback, { backgroundColor: colors.accent + '15' }]}>
                      <Ionicons name="cube-outline" size={20} color={colors.accent} />
                    </View>
                  )}
                  <View style={styles.dealLeft}>
                    <Text style={[styles.dealTitle, { color: colors.text }]} numberOfLines={2}>
                      {deal.listingTitle}
                    </Text>
                    <View style={styles.dealMeta}>
                      <Text style={[styles.dealSource, { color: colors.muted }]}>
                        {deal.listingSource}
                      </Text>
                      {deal.priceVsQ50Pct != null && deal.priceVsQ50Pct < 0 && (
                        <Text style={[styles.dealDiscount, { color: colors.success }]}>
                          {Math.abs(deal.priceVsQ50Pct).toFixed(0)}% below
                        </Text>
                      )}
                    </View>
                  </View>
                  <View style={styles.dealRight}>
                    <Text style={[styles.dealPrice, { color: colors.text }]}>
                      {formatPrice(deal.listingPrice)}
                    </Text>
                    <View style={styles.dealRightRow}>
                      <View style={[styles.dealBadge, { backgroundColor: badge.color + "20" }]}>
                        <Text style={[styles.dealBadgeText, { color: badge.color }]}>
                          {badge.label}
                        </Text>
                      </View>
                      {(deal.status === "discovered" || deal.status === "notified") && (deal.affiliateUrl || deal.listingUrl) && (
                        <AnimatedPressable
                          onPress={() => {
                            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                            collectorsApi.clickDeal(deal.id).catch(() => {});
                            const url = deal.affiliateUrl || deal.listingUrl;
                            if (url) Linking.openURL(url).catch(() => {});
                          }}
                          style={[styles.quickBuyBtn, { backgroundColor: colors.accent }]}
                          accessibilityRole="link"
                          accessibilityLabel={`Open ${deal.listingTitle} listing`}
                        >
                          <Ionicons name="open-outline" size={14} color="#FFFFFF" />
                        </AnimatedPressable>
                      )}
                    </View>
                  </View>
                </AnimatedPressable>
              );
            })}
          </View>
        )}

        {/* Pagination — load older deals on demand. Only shown when we have
            at least one full page AND the BE indicated more pages may exist. */}
        {deals.length >= DEALS_PAGE_SIZE && hasMoreDeals && (
          <AnimatedPressable
            style={[styles.loadMoreBtn, { borderColor: colors.border, backgroundColor: colors.card }]}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              loadMoreDeals();
            }}
            disabled={loadingMore}
            accessibilityRole="button"
            accessibilityLabel="Load more deals"
            accessibilityState={{ busy: loadingMore }}
          >
            <Text style={[styles.loadMoreText, { color: colors.accent }]}>
              {loadingMore ? "Loading…" : "Load more"}
            </Text>
            {!loadingMore && (
              <Ionicons name="chevron-down" size={16} color={colors.accent} />
            )}
          </AnimatedPressable>
        )}

        <View style={{ height: Platform.OS === "ios" ? 24 : 18 }} />
      </ScrollView>
      <QuickNavBar />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  container: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 24 },
  loadingWrap: { flex: 1, alignItems: "center", justifyContent: "center" },

  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 20,
  },
  headerTitle: { fontSize: 22, fontWeight: "700" },
  headerSubtitle: { fontSize: 13, marginTop: 2 },
  createBtn: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    gap: 4,
  },
  createBtnText: { color: "#fff", fontWeight: "700", fontSize: 14 },

  // "Sparrow's watching" status row — pulsing dot + last-scan label
  scanStatus: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 14,
    marginBottom: 18,
  },
  pulseWrap: {
    width: 16,
    height: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  pulseDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  pulseRing: {
    position: "absolute",
    width: 10,
    height: 10,
    borderRadius: 5,
    borderWidth: 2,
  },
  scanStatusTitle: { fontSize: 14, fontWeight: "700" },
  scanStatusSub: { fontSize: 12, marginTop: 2 },

  sectionTitle: { fontSize: 16, fontWeight: "800", marginBottom: 10 },

  // Empty state
  emptyCard: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 24,
    alignItems: "center",
    gap: 8,
    marginBottom: 8,
  },
  emptyTitle: { fontSize: 15, fontWeight: "600" },
  emptySubtitle: { fontSize: 13, textAlign: "center" },
  emptyCtaContainer: { alignItems: "center", marginTop: 16 },
  emptyCtaBtn: {
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 12,
  },
  emptyCtaBtnText: {
    fontSize: 16,
    fontWeight: "600",
    color: "#FFFFFF",
  },

  // Mandate card
  mandateCard: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  mandateHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 6,
  },
  mandateCategoryIcon: {
    width: 32,
    height: 32,
    borderRadius: 9,
    alignItems: "center",
    justifyContent: "center",
  },
  mandateName: { fontSize: 15, fontWeight: "700", flex: 1, marginRight: 8 },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  statusText: { fontSize: 11, fontWeight: "700", textTransform: "uppercase" },
  mandateQuery: { fontSize: 13, marginBottom: 12 },
  mandateStats: { flexDirection: "row", gap: 24, marginBottom: 4 },
  statBlock: { flexDirection: "row", alignItems: "center", gap: 8 },
  statIcon: {
    width: 28,
    height: 28,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  statItem: { alignItems: "center" }, // legacy, kept for safety
  statValue: { fontSize: 15, fontWeight: "800", lineHeight: 18 },
  statLabel: { fontSize: 11, fontWeight: "600", marginTop: 1 },

  budgetBar: { marginTop: 12 },
  budgetTrack: { height: 6, borderRadius: 3, overflow: "hidden" },
  budgetFill: { height: "100%", borderRadius: 3 },
  budgetTextRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 6,
  },
  budgetText: { fontSize: 11 },

  // Deals card
  dealsCard: {
    borderWidth: 1,
    borderRadius: 12,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  dealRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderTopWidth: 1,
    gap: 12,
  },
  dealRowFirst: { borderTopWidth: 0 },
  dealThumb: {
    width: 56,
    height: 56,
    borderRadius: 10,
  },
  dealThumbFallback: {
    alignItems: "center",
    justifyContent: "center",
  },
  dealLeft: { flex: 1, paddingRight: 8 },
  dealTitle: { fontSize: 14, fontWeight: "600", lineHeight: 18 },
  dealMeta: { flexDirection: "row", gap: 8, marginTop: 4, alignItems: "center" },
  dealSource: { fontSize: 12, fontWeight: "500" },
  dealDiscount: { fontSize: 12, fontWeight: "700" },
  dealRight: { alignItems: "flex-end" },
  dealPrice: { fontSize: 15, fontWeight: "800" },
  dealRightRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 4 },
  dealBadge: { paddingHorizontal: 6, paddingVertical: 1, borderRadius: 4 },
  dealBadgeText: { fontSize: 10, fontWeight: "700" },
  quickBuyBtn: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },

  // Pagination
  loadMoreBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 14,
    marginTop: 12,
  },
  loadMoreText: { fontSize: 14, fontWeight: "700" },

  // Skeleton — matches the new layout (scan-status row + mandate cards + deal rows with thumbs)
  skeletonHeader: { height: 28, width: 200, borderRadius: 6, marginBottom: 24, opacity: 0.6 },
  skeletonScan: {
    flexDirection: "row", alignItems: "center", gap: 14,
    borderWidth: 1, borderRadius: 12,
    paddingVertical: 12, paddingHorizontal: 14,
    marginBottom: 18,
  },
  skeletonDot: { width: 16, height: 16, borderRadius: 8 },
  skeletonLine: { height: 14, borderRadius: 4, opacity: 0.6 },
  skeletonCard: {
    borderWidth: 1, borderRadius: 12, padding: 14, marginBottom: 10,
  },
  skeletonIconSquare: { width: 32, height: 32, borderRadius: 9, opacity: 0.6 },
  skeletonDealRow: {
    flexDirection: "row", alignItems: "center", gap: 12,
    paddingVertical: 12, paddingHorizontal: 14,
  },
  skeletonThumb: { width: 56, height: 56, borderRadius: 10, opacity: 0.6 },
});
