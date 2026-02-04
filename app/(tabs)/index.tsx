/**
 * Portfolio Screen — Collectr-style portfolio view with interactive chart.
 *
 * Features:
 * - Tiffany blue (#81D8D0) themed chart
 * - Analytics banner with CTA
 * - Pressable top valued items
 * - Watchlist section with price targets
 */

import React, { useEffect, useMemo, useState, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Platform,
  ActivityIndicator,
  Animated,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { PortfolioLineChart, type TimeSeriesPoint } from "@/components/PortfolioLineChart";
import { useWatchlist } from "@/state/watchlistStore";
import { InboxHeaderButton } from "@/components/InboxHeaderButton";
import { ThemeToggleButton } from "@/components/ThemeToggleButton";
import { useAppTheme } from "@/hooks/useAppTheme";
import { featureFlags } from "@/config/featureFlags";
import { InsightsCard } from "@/components/home/InsightsCard";
import { AlertsCard } from "@/components/home/AlertsCard";
import { usePortfolioInsights } from "@/hooks/usePortfolioInsights";
import { useAlertsFeed } from "@/hooks/useAlertsFeed";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";

// Feature flag check: real mode when EXPO_PUBLIC_SUPABASE_MODE=real
const SUPABASE_MODE = process.env.EXPO_PUBLIC_SUPABASE_MODE ?? "mock";
const USE_REAL_BACKEND = SUPABASE_MODE === "real";

// Keep imports conservative and optional.
let analyticsApi: any = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  analyticsApi = require("@/store/portfolioAnalyticsStore");
} catch {
  analyticsApi = null;
}

// Optional: collectors client for real backend
let collectorsClient: any = null;
if (USE_REAL_BACKEND) {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    collectorsClient = require("@/services/collectorsClient");
  } catch {
    collectorsClient = null;
  }
}

type RangeKey = "1D" | "7D" | "30D";

type ItemRow = {
  id: string;
  name: string;
  category?: string;
  value: number;
  changePct?: number;
};

// ─────────────────────────────────────────────────────────────────────────────
// Formatting helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatMoneyEUR(n: number): string {
  try {
    return new Intl.NumberFormat("nl-NL", {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(n);
  } catch {
    return `€${Math.round(n).toLocaleString("en-US")}`;
  }
}

function formatPct(p?: number): string {
  if (p === undefined || p === null || Number.isNaN(p)) return "—";
  const sign = p > 0 ? "+" : "";
  return `${sign}${(p * 100).toFixed(2)}%`;
}

function formatDeltaEUR(n: number): string {
  const sign = n >= 0 ? "+" : "";
  return `${sign}${formatMoneyEUR(n)}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Data extraction helpers
// ─────────────────────────────────────────────────────────────────────────────

function extractSeries(raw: any): TimeSeriesPoint[] {
  const arr =
    (Array.isArray(raw) && raw) ||
    raw?.points ||
    raw?.series ||
    raw?.data ||
    [];
  if (!Array.isArray(arr)) return [];
  return arr
    .map((p: any, idx: number) => {
      const t = p?.t ?? p?.timestamp ?? new Date().toISOString();
      const v = typeof p?.v === "number" ? p.v : typeof p?.value === "number" ? p.value : Number(p?.y);
      if (typeof v !== "number" || Number.isNaN(v)) return null;
      return { t: String(t), v };
    })
    .filter(Boolean) as TimeSeriesPoint[];
}

function extractItems(raw: any): ItemRow[] {
  const base =
    raw?.items ||
    raw?.holdings ||
    raw?.positions ||
    raw?.snapshot?.items ||
    raw?.snapshot?.holdings ||
    [];
  if (!Array.isArray(base)) return [];
  return base
    .map((it: any, i: number) => {
      const value =
        typeof it?.value === "number"
          ? it.value
          : typeof it?.currentValue === "number"
          ? it.currentValue
          : typeof it?.marketValue === "number"
          ? it.marketValue
          : typeof it?.totalValue === "number"
          ? it.totalValue
          : Number(it?.price ?? 0) * Number(it?.qty ?? 1);

      const name = String(it?.name ?? it?.title ?? it?.displayName ?? `Item ${i + 1}`);
      const id = String(it?.id ?? it?.uuid ?? `${i}`);
      const changePct =
        typeof it?.changePct === "number"
          ? it.changePct
          : typeof it?.change1dPct === "number"
          ? it.change1dPct
          : typeof it?.pctChange === "number"
          ? it.pctChange
          : undefined;

      const category = it?.category ? String(it.category) : undefined;

      if (!Number.isFinite(value)) return null;
      return { id, name, category, value, changePct };
    })
    .filter(Boolean) as ItemRow[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Fallback demo data
// ─────────────────────────────────────────────────────────────────────────────

const FALLBACK_SERIES: TimeSeriesPoint[] = [
  { t: "2025-11-01T00:00:00Z", v: 12400 },
  { t: "2025-11-03T00:00:00Z", v: 12340 },
  { t: "2025-11-06T00:00:00Z", v: 12510 },
  { t: "2025-11-09T00:00:00Z", v: 12680 },
  { t: "2025-11-12T00:00:00Z", v: 12590 },
  { t: "2025-11-15T00:00:00Z", v: 12840 },
  { t: "2025-11-18T00:00:00Z", v: 13120 },
  { t: "2025-11-21T00:00:00Z", v: 13040 },
  { t: "2025-11-24T00:00:00Z", v: 13310 },
  { t: "2025-11-27T00:00:00Z", v: 13480 },
  { t: "2025-11-29T00:00:00Z", v: 13290 },
  { t: "2025-11-30T00:00:00Z", v: 13610 },
];

const FALLBACK_ITEMS: ItemRow[] = [
  { id: "1", name: "PSA 10 Lugia (Neo Genesis)", category: "Pokémon", value: 3450, changePct: 0.028 },
  { id: "2", name: "Gunpla MG Barbatos (built)", category: "Gunpla", value: 1820, changePct: -0.011 },
  { id: "3", name: "Funko: Vaulted Grail", category: "Funko", value: 1250, changePct: 0.007 },
  { id: "4", name: "Warhammer Army Lot", category: "Warhammer", value: 980, changePct: 0.014 },
  { id: "5", name: "Designer Toy (limited run)", category: "Art Toys", value: 760, changePct: -0.006 },
];

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export default function PortfolioScreen() {
  const router = useRouter();
  const watchlist = useWatchlist();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  const [range, setRange] = useState<RangeKey>("7D");
  const [series, setSeries] = useState<TimeSeriesPoint[]>(FALLBACK_SERIES);
  const [items, setItems] = useState<ItemRow[]>(FALLBACK_ITEMS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Data insights & alerts (feature flagged)
  const { insights } = usePortfolioInsights({
    period: range.toLowerCase() as '7d' | '30d',
    enabled: featureFlags.FEATURE_DATA_INSIGHTS_ALERTS
  });
  const { alerts, markAsRead } = useAlertsFeed({
    limit: 5,
    enabled: featureFlags.FEATURE_DATA_INSIGHTS_ALERTS
  });

  // Get watchlist items with their alerts
  const watchlistItems = useMemo(() => {
    return watchlist.items.slice(0, 5).map((item) => ({
      ...item,
      alert: watchlist.getAlert(item.id),
    }));
  }, [watchlist]);

  // Compute totals from series
  const { total, delta, deltaPct } = useMemo(() => {
    if (!series.length) {
      return { total: 0, delta: 0, deltaPct: 0 };
    }
    const sorted = [...series].sort(
      (a, b) => new Date(a.t).getTime() - new Date(b.t).getTime()
    );
    const startVal = sorted[0].v;
    const endVal = sorted[sorted.length - 1].v;
    const d = endVal - startVal;
    const pct = startVal > 0 ? d / startVal : 0;
    return { total: endVal, delta: d, deltaPct: pct };
  }, [series]);

  // Load data based on mode and range
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Pass 2 (C): Real backend wiring
      if (USE_REAL_BACKEND && collectorsClient?.getPortfolioTimeseries) {
        try {
          const rangeParam = range.toLowerCase() as "1d" | "7d" | "30d";
          const timeseriesData = await collectorsClient.getPortfolioTimeseries(rangeParam);
          const extractedSeries = extractSeries(timeseriesData);
          if (extractedSeries.length) {
            setSeries(extractedSeries);
          } else {
            setSeries(FALLBACK_SERIES);
          }

          if (collectorsClient?.getPortfolioItems) {
            const itemsData = await collectorsClient.getPortfolioItems();
            const extractedItems = extractItems(itemsData);
            if (extractedItems.length) {
              setItems(extractedItems.sort((a, b) => b.value - a.value));
            } else {
              setItems(FALLBACK_ITEMS);
            }
          }
        } catch (realErr: any) {
          console.warn("[Portfolio] Real backend error, falling back:", realErr);
          setError("Could not load real data. Showing demo.");
          setSeries(FALLBACK_SERIES);
          setItems(FALLBACK_ITEMS);
        }
      } else {
        // Mock mode: use analytics store or fallback
        if (analyticsApi?.fetchPortfolioSnapshot) {
          try {
            const snap = await analyticsApi.fetchPortfolioSnapshot();
            const extractedSeries = extractSeries(snap?.series || snap);
            const extractedItems = extractItems(snap);

            setSeries(extractedSeries.length ? extractedSeries : FALLBACK_SERIES);
            setItems(
              extractedItems.length
                ? extractedItems.sort((a, b) => b.value - a.value)
                : FALLBACK_ITEMS
            );
          } catch (mockErr) {
            console.warn("[Portfolio] Mock store error:", mockErr);
            setSeries(FALLBACK_SERIES);
            setItems(FALLBACK_ITEMS);
          }
        } else {
          // No store available, use fallback
          setSeries(FALLBACK_SERIES);
          setItems(FALLBACK_ITEMS);
        }
      }
    } catch (err: any) {
      console.warn("[Portfolio] Unexpected error:", err);
      setError("Failed to load portfolio data.");
      setSeries(FALLBACK_SERIES);
      setItems(FALLBACK_ITEMS);
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Determine if positive or negative
  const isPositive = deltaPct >= 0;

  const rangeButtons: RangeKey[] = ["1D", "7D", "30D"];

  // Navigate to item detail
  const handleItemPress = (item: ItemRow) => {
    router.push({
      pathname: "/item/[id]",
      params: {
        id: item.id,
        name: item.name,
        category: item.category ?? "",
        value: String(item.value),
      },
    });
  };

  // Navigate to analytics
  const handleAnalyticsPress = () => {
    router.push("/analytics");
  };

  // Navigate to watchlist
  const handleWatchlistPress = () => {
    router.push("/watchlist-builder");
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={["top", "left", "right"]}>
      <ScrollView
        contentContainerStyle={[styles.container, { backgroundColor: colors.background }]}
        showsVerticalScrollIndicator={false}
      >
        <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
        {/* Header */}
        <View style={styles.headerRow}>
          <View style={styles.headerLeft}>
            <Text style={[styles.headerTitle, { color: colors.text }]}>Portfolio</Text>
            <Text style={[styles.headerSubtitle, { color: colors.muted }]}>Track your collection value.</Text>
          </View>
          <View style={styles.headerIcons}>
            <InboxHeaderButton color={colors.text} size={22} />
            <ThemeToggleButton size={22} />
          </View>
        </View>

        {/* Collection Value */}
        <View style={styles.valueSection}>
          <Text style={[styles.headerLabel, { color: colors.muted }]}>COLLECTION VALUE</Text>
          <Text style={[styles.totalValue, { color: colors.text }]}>{formatMoneyEUR(total)}</Text>
          <Text style={[styles.deltaText, { color: isPositive ? '#10B981' : '#EF4444' }]}>
            {formatDeltaEUR(delta)} ({formatPct(deltaPct)})
          </Text>
        </View>

        {/* Range Toggles */}
        <View style={styles.rangeRow}>
          {rangeButtons.map((k) => {
            const active = k === range;
            return (
              <AnimatedPressable
                key={k}
                accessibilityRole="button"
                onPress={() => {
                  if (k !== range) {
                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  }
                  setRange(k);
                }}
                style={[
                  styles.rangeBtn,
                  { backgroundColor: colors.card, borderColor: colors.border },
                  active && { backgroundColor: colors.accent + '20', borderColor: colors.accent },
                ]}
              >
                <Text style={[styles.rangeText, { color: colors.muted }, active && { color: colors.text }]}>
                  {k}
                </Text>
              </AnimatedPressable>
            );
          })}
        </View>

        {/* Chart Card with Interactive Line Chart */}
        <View style={[styles.chartCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          {loading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="small" color={colors.accent} />
              <Text style={[styles.loadingText, { color: colors.muted }]}>Loading...</Text>
            </View>
          ) : (
            <PortfolioLineChart
              series={series}
              accentColor={colors.accent}
              showValueHeader={true}
              showAxisLabels={true}
              axisLabelColor={colors.muted}
            />
          )}
        </View>

        {/* Error message (if any) */}
        {error && (
          <View style={[styles.errorBanner, { backgroundColor: '#FEF2F2' }]}>
            <Ionicons name="warning-outline" size={14} color="#EF4444" />
            <Text style={[styles.errorText, { color: '#EF4444' }]}>{error}</Text>
          </View>
        )}

        {/* Mode indicator (dev only) */}
        {__DEV__ && (
          <Text style={[styles.modeIndicator, { color: colors.muted }]}>
            Mode: {USE_REAL_BACKEND ? "REAL" : "MOCK"}
          </Text>
        )}

        {/* Watchlist Card (always show - has empty state) */}
        {featureFlags.FEATURE_DATA_INSIGHTS_ALERTS && (
          <AlertsCard
            alerts={alerts}
            onAlertPress={(alert) => {
              markAsRead(alert.id);
              router.push({ pathname: '/item/[id]', params: { id: alert.itemId } });
            }}
            onStartWatchlist={handleWatchlistPress}
            showEmptyState={true}
          />
        )}
        {featureFlags.FEATURE_DATA_INSIGHTS_ALERTS && insights && (
          <InsightsCard
            insights={insights}
            onViewDetails={handleAnalyticsPress}
          />
        )}

        {/* Collection Section Header */}
        <View style={styles.sectionHeader}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Collection</Text>
          <Text style={[styles.sectionCount, { color: colors.muted }]}>
            {items.length} {items.length === 1 ? "item" : "items"}
          </Text>
        </View>

        {/* Value-Ranked Items List - Pressable Cards */}
        <View style={[styles.listCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          {items.slice(0, 12).map((it, idx) => {
            const itemUp = (it.changePct ?? 0) >= 0;
            return (
              <AnimatedPressable
                key={it.id}
                style={[
                  styles.itemRow,
                  { borderTopColor: colors.border },
                  idx === 0 && styles.itemRowFirst,
                ]}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  handleItemPress(it);
                }}
                accessibilityRole="button"
                accessibilityLabel={`View ${it.name}`}
              >
                <View style={styles.itemLeft}>
                  <Text style={[styles.itemName, { color: colors.text }]} numberOfLines={1}>
                    {it.name}
                  </Text>
                  <Text style={[styles.itemCategory, { color: colors.muted }]} numberOfLines={1}>
                    {it.category ?? "—"}
                  </Text>
                </View>
                <View style={styles.itemRight}>
                  <Text style={[styles.itemValue, { color: colors.text }]}>{formatMoneyEUR(it.value)}</Text>
                  <Text style={[styles.itemPct, { color: itemUp ? '#10B981' : '#EF4444' }]}>
                    {formatPct(it.changePct)}
                  </Text>
                </View>
              </AnimatedPressable>
            );
          })}
        </View>

        {/* Watchlist Section */}
        {watchlistItems.length > 0 && (
          <>
            <View style={styles.sectionHeader}>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Watchlist</Text>
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  handleWatchlistPress();
                }}
                accessibilityRole="link"
              >
                <Text style={[styles.seeAllLink, { color: colors.accent }]}>See all →</Text>
              </AnimatedPressable>
            </View>

            <View style={[styles.listCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
              {watchlistItems.map((it, idx) => {
                const hasAlert = Boolean(it.alert);
                const targetPrice = it.alert?.threshold;
                const currentValue = it.currentValue ?? it.value ?? 0;

                return (
                  <AnimatedPressable
                    key={it.id}
                    style={[
                      styles.watchlistRow,
                      { borderTopColor: colors.border },
                      idx === 0 && styles.itemRowFirst,
                    ]}
                    onPress={() => {
                      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                      handleWatchlistPress();
                    }}
                    accessibilityRole="button"
                    accessibilityLabel={`Watchlist item: ${it.name ?? it.title}`}
                  >
                    <View style={styles.watchlistLeft}>
                      <View style={styles.watchlistNameRow}>
                        <Ionicons
                          name={hasAlert ? "notifications" : "notifications-outline"}
                          size={16}
                          color={hasAlert ? colors.accent : colors.muted}
                          style={styles.bellIcon}
                        />
                        <Text style={[styles.itemName, { color: colors.text }]} numberOfLines={1}>
                          {it.name ?? it.title ?? "Watchlist Item"}
                        </Text>
                      </View>
                      <Text style={[styles.itemCategory, { color: colors.muted }]} numberOfLines={1}>
                        {it.category ?? "—"}
                      </Text>
                    </View>
                    <View style={styles.watchlistRight}>
                      {targetPrice != null && (
                        <Text style={[styles.targetPrice, { color: colors.accent }]}>
                          Target {formatMoneyEUR(targetPrice)}
                        </Text>
                      )}
                      <Text style={[styles.currentPrice, { color: colors.muted }]}>
                        Current {formatMoneyEUR(currentValue)}
                      </Text>
                    </View>
                  </AnimatedPressable>
                );
              })}
            </View>
          </>
        )}

        {/* Watchlist Empty State - Now shown in AlertsCard above */}

        {/* Bottom spacing */}
        <View style={{ height: Platform.OS === "ios" ? 24 : 18 }} />
        </Animated.View>
      </ScrollView>
    </SafeAreaView>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Colors & Styles (Collectr Design Tokens)
// ─────────────────────────────────────────────────────────────────────────────

const COLORS = {
  // Brand
  tiffany: "#81D8D0",
  tiffanyDark: "#5FBFB6",
  tiffanyLight: "#E6F7F5",

  // Core
  background: "#F7FAF9",
  card: "#FFFFFF",
  navy: "#0F172A",
  muted: "#64748B",
  border: "#E2E8F0",

  // Status
  success: "#10B981",
  warning: "#F59E0B",
  danger: "#EF4444",

  // Banners
  analyticsBg: "#E5F4F8",
  analyticsBorder: "#B4DDE7",
  analyticsAccent: "#00A3C4",
};

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  container: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 24,
  },

  // Header
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 16,
  },
  headerLeft: {
    flex: 1,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: "700",
  },
  headerSubtitle: {
    fontSize: 12,
    marginTop: 4,
  },
  headerIcons: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  valueSection: {
    marginBottom: 16,
  },
  headerLabel: {
    color: COLORS.muted,
    fontSize: 12,
    fontWeight: "600",
    marginBottom: 4,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  totalValue: {
    color: COLORS.navy,
    fontSize: 36,
    fontWeight: "800",
    letterSpacing: -0.5,
  },
  deltaText: {
    fontSize: 15,
    fontWeight: "700",
    marginTop: 4,
  },
  deltaUp: {
    color: COLORS.success,
  },
  deltaDown: {
    color: COLORS.danger,
  },

  // Range toggles
  rangeRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 12,
  },
  rangeBtn: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    backgroundColor: COLORS.card,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 8,
  },
  rangeBtnActive: {
    backgroundColor: COLORS.tiffanyLight,
    borderColor: COLORS.tiffany,
  },
  rangeText: {
    color: COLORS.muted,
    fontWeight: "700",
    fontSize: 13,
  },
  rangeTextActive: {
    color: COLORS.navy,
  },

  // Chart card
  chartCard: {
    backgroundColor: COLORS.card,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    minHeight: 220,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 190,
  },
  loadingText: {
    color: COLORS.muted,
    fontSize: 12,
    marginTop: 8,
  },

  // Error
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "#FEF2F2",
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    marginBottom: 12,
  },
  errorText: {
    color: COLORS.danger,
    fontSize: 12,
    fontWeight: "500",
  },

  // Mode indicator (dev)
  modeIndicator: {
    fontSize: 10,
    color: COLORS.muted,
    textAlign: "center",
    marginBottom: 8,
  },

  // Analytics Banner
  analyticsBanner: {
    backgroundColor: COLORS.analyticsBg,
    borderWidth: 1,
    borderColor: COLORS.analyticsBorder,
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  analyticsBannerLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
  },
  analyticsIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: COLORS.card,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  analyticsBannerText: {
    flex: 1,
  },
  analyticsBannerTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: COLORS.navy,
    marginBottom: 2,
  },
  analyticsBannerSubtitle: {
    fontSize: 12,
    color: COLORS.muted,
  },
  analyticsBannerBtn: {
    backgroundColor: COLORS.analyticsAccent,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    marginLeft: 12,
  },
  analyticsBannerBtnText: {
    color: COLORS.card,
    fontSize: 13,
    fontWeight: "600",
  },

  // Section header
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: COLORS.navy,
  },
  sectionCount: {
    fontSize: 13,
    fontWeight: "600",
    color: COLORS.muted,
  },
  seeAllLink: {
    fontSize: 13,
    fontWeight: "600",
    color: COLORS.tiffanyDark,
  },

  // Items list
  listCard: {
    backgroundColor: COLORS.card,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 12,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
    marginBottom: 20,
  },
  itemRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  itemRowFirst: {
    borderTopWidth: 0,
  },
  itemRowPressed: {
    backgroundColor: COLORS.tiffanyLight,
  },
  itemLeft: {
    flex: 1,
    paddingRight: 12,
  },
  itemName: {
    color: COLORS.navy,
    fontWeight: "700",
    fontSize: 14,
  },
  itemCategory: {
    color: COLORS.muted,
    fontWeight: "600",
    fontSize: 12,
    marginTop: 2,
  },
  itemRight: {
    alignItems: "flex-end",
    minWidth: 90,
  },
  itemValue: {
    color: COLORS.navy,
    fontWeight: "800",
    fontSize: 14,
  },
  itemPct: {
    fontWeight: "700",
    fontSize: 12,
    marginTop: 2,
  },
  pctUp: {
    color: COLORS.success,
  },
  pctDown: {
    color: COLORS.danger,
  },

  // Watchlist rows
  watchlistRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  watchlistLeft: {
    flex: 1,
    paddingRight: 12,
  },
  watchlistNameRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  bellIcon: {
    marginRight: 6,
  },
  watchlistRight: {
    alignItems: "flex-end",
    minWidth: 100,
  },
  targetPrice: {
    color: COLORS.tiffanyDark,
    fontWeight: "700",
    fontSize: 13,
  },
  currentPrice: {
    color: COLORS.muted,
    fontWeight: "600",
    fontSize: 12,
    marginTop: 2,
  },

  // Watchlist empty state
  watchlistEmptyBanner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: COLORS.card,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
  },
  watchlistEmptyText: {
    flex: 1,
    marginLeft: 12,
  },
  watchlistEmptyTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: COLORS.navy,
    marginBottom: 2,
  },
  watchlistEmptySubtitle: {
    fontSize: 12,
    color: COLORS.muted,
  },
});
