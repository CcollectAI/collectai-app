/**
 * Portfolio Analytics Screen — Pro-grade analytics dashboard
 *
 * Features:
 * - P/L summary with max drawdown
 * - Portfolio tier badge (Diamond/Gold/Silver)
 * - Category allocations visualization
 * - Winners & losers section
 * - Full items breakdown
 */

import React, { useEffect, useState, useMemo } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Pressable,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Stack, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

// Import analytics store
import {
  fetchPortfolioSnapshot,
  type PortfolioSnapshot,
} from "@/store/portfolioAnalyticsStore";

// ─────────────────────────────────────────────────────────────────────────────
// Design Tokens (Collectr)
// ─────────────────────────────────────────────────────────────────────────────

const COLORS = {
  tiffany: "#81D8D0",
  tiffanyDark: "#5FBFB6",
  tiffanyLight: "#E6F7F5",
  background: "#F7FAF9",
  card: "#FFFFFF",
  navy: "#0F172A",
  muted: "#64748B",
  border: "#E2E8F0",
  success: "#10B981",
  warning: "#F59E0B",
  danger: "#EF4444",
  diamond: "#A78BFA",
  gold: "#FBBF24",
  silver: "#94A3B8",
};

const TIER_COLORS: Record<string, string> = {
  Diamond: COLORS.diamond,
  Gold: COLORS.gold,
  Silver: COLORS.silver,
  Unranked: COLORS.muted,
};

const TIER_ICONS: Record<string, string> = {
  Diamond: "diamond-outline",
  Gold: "trophy-outline",
  Silver: "medal-outline",
  Unranked: "help-circle-outline",
};

// ─────────────────────────────────────────────────────────────────────────────
// Formatting helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatCurrency(n: number): string {
  try {
    return new Intl.NumberFormat("nl-NL", {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(n);
  } catch {
    return `€${Math.round(n).toLocaleString()}`;
  }
}

function formatPct(p: number, includeSign = true): string {
  const sign = includeSign && p > 0 ? "+" : "";
  return `${sign}${(p * 100).toFixed(2)}%`;
}

function formatScore(s: number): string {
  return `${Math.round(s * 100)}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export default function AnalyticsScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPortfolioSnapshot();
      setSnapshot(data);
    } catch (err: any) {
      console.warn("[Analytics] Error loading snapshot:", err);
      setError(err?.message || "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  };

  // Derived data
  const { pl, allocations, winnersLosers, tierSummary, items } = snapshot ?? {
    pl: null,
    allocations: [],
    winnersLosers: { winners: [], losers: [], neutral: [] },
    tierSummary: null,
    items: [],
  };

  const isPositive = (pl?.deltaPct ?? 0) >= 0;

  // Category colors for allocation bars
  const categoryColors = useMemo(() => {
    const colors = ["#81D8D0", "#5FBFB6", "#44A9A1", "#2D8A84", "#1F6B66"];
    const map: Record<string, string> = {};
    allocations.forEach((a, i) => {
      map[a.category] = colors[i % colors.length];
    });
    return map;
  }, [allocations]);

  if (loading) {
    return (
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
        <Stack.Screen options={{ headerShown: false }} />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={COLORS.tiffany} />
          <Text style={styles.loadingText}>Loading analytics...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
      <Stack.Screen options={{ headerShown: false }} />
      <ScrollView
        contentContainerStyle={styles.container}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <Pressable
            style={styles.backBtn}
            onPress={() => router.back()}
            accessibilityLabel="Go back"
          >
            <Ionicons name="chevron-back" size={24} color={COLORS.navy} />
          </Pressable>
          <View style={styles.headerText}>
            <Text style={styles.headerLabel}>PORTFOLIO</Text>
            <Text style={styles.headerTitle}>Analytics</Text>
          </View>
          <Pressable style={styles.refreshBtn} onPress={loadData}>
            <Ionicons name="refresh-outline" size={20} color={COLORS.muted} />
          </Pressable>
        </View>

        {/* Error Banner */}
        {error && (
          <View style={styles.errorBanner}>
            <Ionicons name="warning-outline" size={16} color={COLORS.danger} />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        {/* P/L Summary Card */}
        {pl && (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>Performance</Text>
              <View style={[styles.badge, isPositive ? styles.badgeSuccess : styles.badgeDanger]}>
                <Text style={[styles.badgeText, isPositive ? styles.badgeTextSuccess : styles.badgeTextDanger]}>
                  {formatPct(pl.deltaPct)}
                </Text>
              </View>
            </View>

            <View style={styles.metricsGrid}>
              <View style={styles.metricItem}>
                <Text style={styles.metricLabel}>Current Value</Text>
                <Text style={styles.metricValue}>{formatCurrency(pl.currentValue)}</Text>
              </View>
              <View style={styles.metricItem}>
                <Text style={styles.metricLabel}>Starting Value</Text>
                <Text style={styles.metricValueMuted}>{formatCurrency(pl.startValue)}</Text>
              </View>
              <View style={styles.metricItem}>
                <Text style={styles.metricLabel}>Total Gain/Loss</Text>
                <Text style={[styles.metricValue, isPositive ? styles.textSuccess : styles.textDanger]}>
                  {pl.deltaAbs >= 0 ? "+" : ""}{formatCurrency(pl.deltaAbs)}
                </Text>
              </View>
              <View style={styles.metricItem}>
                <Text style={styles.metricLabel}>Max Drawdown</Text>
                <Text style={[styles.metricValue, styles.textDanger]}>
                  {formatPct(pl.maxDrawdownPct, false)}
                </Text>
              </View>
            </View>
          </View>
        )}

        {/* Portfolio Tier Card */}
        {tierSummary && (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>Portfolio Tier</Text>
            </View>

            <View style={styles.tierBadgeContainer}>
              <View style={[styles.tierBadge, { backgroundColor: TIER_COLORS[tierSummary.tier] + "20" }]}>
                <Ionicons
                  name={TIER_ICONS[tierSummary.tier] as any}
                  size={28}
                  color={TIER_COLORS[tierSummary.tier]}
                />
                <Text style={[styles.tierLabel, { color: TIER_COLORS[tierSummary.tier] }]}>
                  {tierSummary.tier}
                </Text>
              </View>
            </View>

            <View style={styles.scoresRow}>
              <View style={styles.scoreItem}>
                <Text style={styles.scoreValue}>{formatScore(tierSummary.rarityScore)}</Text>
                <Text style={styles.scoreLabel}>Rarity</Text>
              </View>
              <View style={styles.scoreDivider} />
              <View style={styles.scoreItem}>
                <Text style={styles.scoreValue}>{formatScore(tierSummary.completenessScore)}</Text>
                <Text style={styles.scoreLabel}>Completeness</Text>
              </View>
              <View style={styles.scoreDivider} />
              <View style={styles.scoreItem}>
                <Text style={styles.scoreValue}>{formatScore(tierSummary.diversificationScore)}</Text>
                <Text style={styles.scoreLabel}>Diversity</Text>
              </View>
            </View>
          </View>
        )}

        {/* Category Allocations */}
        {allocations.length > 0 && (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>Allocations</Text>
              <Text style={styles.cardSubtitle}>{allocations.length} categories</Text>
            </View>

            {/* Allocation Bar */}
            <View style={styles.allocationBar}>
              {allocations.map((a) => (
                <View
                  key={a.category}
                  style={[
                    styles.allocationSegment,
                    {
                      flex: a.weight,
                      backgroundColor: categoryColors[a.category],
                    },
                  ]}
                />
              ))}
            </View>

            {/* Allocation List */}
            <View style={styles.allocationList}>
              {allocations.slice(0, 6).map((a) => (
                <View key={a.category} style={styles.allocationRow}>
                  <View style={styles.allocationLeft}>
                    <View style={[styles.allocationDot, { backgroundColor: categoryColors[a.category] }]} />
                    <Text style={styles.allocationName}>{a.category}</Text>
                  </View>
                  <View style={styles.allocationRight}>
                    <Text style={styles.allocationValue}>{formatCurrency(a.totalValue)}</Text>
                    <Text style={styles.allocationPct}>{formatPct(a.weight, false)}</Text>
                  </View>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* Winners & Losers */}
        {(winnersLosers.winners.length > 0 || winnersLosers.losers.length > 0) && (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>Movers</Text>
              <Text style={styles.cardSubtitle}>24h change</Text>
            </View>

            {/* Winners */}
            {winnersLosers.winners.length > 0 && (
              <View style={styles.moversSection}>
                <View style={styles.moversSectionHeader}>
                  <Ionicons name="trending-up" size={16} color={COLORS.success} />
                  <Text style={[styles.moversSectionTitle, { color: COLORS.success }]}>Winners</Text>
                </View>
                {winnersLosers.winners.slice(0, 3).map((item) => (
                  <View key={item.id} style={styles.moverRow}>
                    <Text style={styles.moverName} numberOfLines={1}>{item.name}</Text>
                    <Text style={[styles.moverPct, styles.textSuccess]}>
                      {formatPct(item.change1dPct ?? 0)}
                    </Text>
                  </View>
                ))}
              </View>
            )}

            {/* Losers */}
            {winnersLosers.losers.length > 0 && (
              <View style={styles.moversSection}>
                <View style={styles.moversSectionHeader}>
                  <Ionicons name="trending-down" size={16} color={COLORS.danger} />
                  <Text style={[styles.moversSectionTitle, { color: COLORS.danger }]}>Losers</Text>
                </View>
                {winnersLosers.losers.slice(0, 3).map((item) => (
                  <View key={item.id} style={styles.moverRow}>
                    <Text style={styles.moverName} numberOfLines={1}>{item.name}</Text>
                    <Text style={[styles.moverPct, styles.textDanger]}>
                      {formatPct(item.change1dPct ?? 0)}
                    </Text>
                  </View>
                ))}
              </View>
            )}
          </View>
        )}

        {/* Items Summary */}
        {items.length > 0 && (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>Holdings</Text>
              <Text style={styles.cardSubtitle}>{items.length} items</Text>
            </View>

            {items.slice(0, 8).map((item, idx) => (
              <View
                key={item.id}
                style={[styles.itemRow, idx === 0 && styles.itemRowFirst]}
              >
                <View style={styles.itemLeft}>
                  <Text style={styles.itemName} numberOfLines={1}>{item.name}</Text>
                  <Text style={styles.itemCategory}>{item.category}</Text>
                </View>
                <View style={styles.itemRight}>
                  <Text style={styles.itemValue}>{formatCurrency(item.currentValue)}</Text>
                  {item.change1dPct !== undefined && (
                    <Text
                      style={[
                        styles.itemPct,
                        (item.change1dPct ?? 0) >= 0 ? styles.textSuccess : styles.textDanger,
                      ]}
                    >
                      {formatPct(item.change1dPct)}
                    </Text>
                  )}
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Bottom spacing */}
        <View style={{ height: 32 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  container: {
    paddingHorizontal: 16,
    paddingBottom: 24,
  },
  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  loadingText: {
    marginTop: 12,
    color: COLORS.muted,
    fontSize: 14,
  },

  // Header
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 16,
  },
  backBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: -8,
  },
  headerText: {
    flex: 1,
    marginLeft: 4,
  },
  headerLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: COLORS.muted,
    letterSpacing: 0.5,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: "800",
    color: COLORS.navy,
  },
  refreshBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },

  // Error
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: "#FEF2F2",
    padding: 12,
    borderRadius: 12,
    marginBottom: 16,
  },
  errorText: {
    color: COLORS.danger,
    fontSize: 13,
    flex: 1,
  },

  // Cards
  card: {
    backgroundColor: COLORS.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 16,
    marginBottom: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: COLORS.navy,
  },
  cardSubtitle: {
    fontSize: 13,
    color: COLORS.muted,
  },

  // Badge
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  badgeSuccess: {
    backgroundColor: "#ECFDF5",
  },
  badgeDanger: {
    backgroundColor: "#FEF2F2",
  },
  badgeText: {
    fontSize: 13,
    fontWeight: "700",
  },
  badgeTextSuccess: {
    color: COLORS.success,
  },
  badgeTextDanger: {
    color: COLORS.danger,
  },

  // Metrics Grid
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  metricItem: {
    width: "50%",
    marginBottom: 16,
  },
  metricLabel: {
    fontSize: 12,
    color: COLORS.muted,
    marginBottom: 4,
  },
  metricValue: {
    fontSize: 18,
    fontWeight: "700",
    color: COLORS.navy,
  },
  metricValueMuted: {
    fontSize: 18,
    fontWeight: "700",
    color: COLORS.muted,
  },

  // Text colors
  textSuccess: {
    color: COLORS.success,
  },
  textDanger: {
    color: COLORS.danger,
  },

  // Tier
  tierBadgeContainer: {
    alignItems: "center",
    marginBottom: 20,
  },
  tierBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 24,
  },
  tierLabel: {
    fontSize: 20,
    fontWeight: "800",
  },
  scoresRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  scoreItem: {
    alignItems: "center",
    flex: 1,
  },
  scoreValue: {
    fontSize: 24,
    fontWeight: "800",
    color: COLORS.navy,
  },
  scoreLabel: {
    fontSize: 11,
    color: COLORS.muted,
    marginTop: 2,
  },
  scoreDivider: {
    width: 1,
    height: 32,
    backgroundColor: COLORS.border,
  },

  // Allocations
  allocationBar: {
    flexDirection: "row",
    height: 8,
    borderRadius: 4,
    overflow: "hidden",
    marginBottom: 16,
  },
  allocationSegment: {
    minWidth: 4,
  },
  allocationList: {
    gap: 12,
  },
  allocationRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  allocationLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
  },
  allocationDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 10,
  },
  allocationName: {
    fontSize: 14,
    fontWeight: "600",
    color: COLORS.navy,
  },
  allocationRight: {
    alignItems: "flex-end",
  },
  allocationValue: {
    fontSize: 14,
    fontWeight: "700",
    color: COLORS.navy,
  },
  allocationPct: {
    fontSize: 12,
    color: COLORS.muted,
  },

  // Movers
  moversSection: {
    marginBottom: 16,
  },
  moversSectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 10,
  },
  moversSectionTitle: {
    fontSize: 13,
    fontWeight: "700",
  },
  moverRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  moverName: {
    flex: 1,
    fontSize: 14,
    color: COLORS.navy,
    marginRight: 12,
  },
  moverPct: {
    fontSize: 14,
    fontWeight: "700",
  },

  // Items
  itemRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  itemRowFirst: {
    borderTopWidth: 0,
  },
  itemLeft: {
    flex: 1,
    marginRight: 12,
  },
  itemName: {
    fontSize: 14,
    fontWeight: "600",
    color: COLORS.navy,
  },
  itemCategory: {
    fontSize: 12,
    color: COLORS.muted,
    marginTop: 2,
  },
  itemRight: {
    alignItems: "flex-end",
  },
  itemValue: {
    fontSize: 14,
    fontWeight: "700",
    color: COLORS.navy,
  },
  itemPct: {
    fontSize: 12,
    fontWeight: "600",
    marginTop: 2,
  },
});
