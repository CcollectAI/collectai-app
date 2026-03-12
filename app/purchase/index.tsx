/**
 * Agent Hub — Smart Deal Agent main screen.
 *
 * Shows active mandates as cards, recent deals feed, and create mandate button.
 */

import React, { useEffect, useState, useCallback } from "react";
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Linking,
  RefreshControl,
  Platform,
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
import { SkeletonList } from "@/components/Skeleton";
import { QuickNavBar } from "@/components/QuickNavBar";
import type { PurchaseMandate, MandateDeal } from "@/data/types";

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
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const [mandateRes, dealRes] = await Promise.all([
        collectorsApi.listMandates(20, 0),
        collectorsApi.listDeals({ limit: 10, offset: 0 }),
      ]);
      const mandateData = mandateRes as { mandates?: typeof mandates } | undefined;
      const dealData = dealRes as { deals?: typeof deals } | undefined;
      setMandates(mandateData?.mandates ?? []);
      setDeals(dealData?.deals ?? []);
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
        <View style={styles.loadingWrap}>
          <SkeletonList count={3} type="deal" />
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
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
        }
      >
        {/* Header */}
        <View style={styles.headerRow}>
          <View>
            <Text style={[styles.headerTitle, { color: colors.text }]}>Deal Agent</Text>
            <Text style={[styles.headerSubtitle, { color: colors.muted }]}>
              Your always-on deal finder.
            </Text>
          </View>
          <AnimatedPressable
            style={[styles.createBtn, { backgroundColor: colors.accent }]}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              router.push("/purchase/create-mandate");
            }}
            accessibilityRole="button"
            accessibilityLabel="Create new search"
          >
            <Ionicons name="add" size={20} color="#fff" />
            <Text style={styles.createBtnText}>New</Text>
          </AnimatedPressable>
        </View>

        {/* Active Mandates */}
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Active Searches</Text>

        {mandates.length === 0 ? (
          <View style={[styles.emptyCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Ionicons name="search-outline" size={32} color={colors.muted} />
            <Text style={[styles.emptyTitle, { color: colors.text }]}>No searches yet</Text>
            <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
              Set up a search to find deals automatically.
            </Text>
            <View style={styles.emptyCtaContainer}>
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  router.push("/purchase/create-mandate");
                }}
                style={[styles.emptyCtaBtn, { backgroundColor: colors.accent }]}
                accessibilityRole="button"
                accessibilityLabel="Set up a deal mandate"
              >
                <Text style={styles.emptyCtaBtnText}>Set Up a Deal Mandate</Text>
              </AnimatedPressable>
            </View>
          </View>
        ) : (
          mandates.map((m) => {
            const budgetPct = m.maxTotalBudget
              ? Math.min(1, m.spentTotal / m.maxTotalBudget)
              : 0;

            return (
              <AnimatedPressable
                key={m.id}
                style={[styles.mandateCard, { backgroundColor: colors.card, borderColor: colors.border }]}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  router.push(`/purchase/create-mandate?id=${m.id}`);
                }}
                accessibilityRole="button"
                accessibilityLabel={`Search: ${m.name}`}
              >
                <View style={styles.mandateHeader}>
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

                <View style={styles.mandateStats}>
                  <View style={styles.statItem}>
                    <Text style={[styles.statValue, { color: colors.text }]}>{m.dealsFound}</Text>
                    <Text style={[styles.statLabel, { color: colors.muted }]}>Found</Text>
                  </View>
                  <View style={styles.statItem}>
                    <Text style={[styles.statValue, { color: colors.text }]}>{m.dealsPurchased}</Text>
                    <Text style={[styles.statLabel, { color: colors.muted }]}>Bought</Text>
                  </View>
                  <View style={styles.statItem}>
                    <Text style={[styles.statValue, { color: colors.text }]}>
                      {formatPrice(m.maxPrice)}
                    </Text>
                    <Text style={[styles.statLabel, { color: colors.muted }]}>Max</Text>
                  </View>
                </View>

                {m.maxTotalBudget != null && (
                  <View style={styles.budgetBar}>
                    <View style={[styles.budgetTrack, { backgroundColor: colors.border }]}>
                      <View
                        style={[
                          styles.budgetFill,
                          {
                            backgroundColor: budgetPct > 0.8 ? colors.warning : colors.accent,
                            width: `${budgetPct * 100}%`,
                          },
                        ]}
                      />
                    </View>
                    <Text style={[styles.budgetText, { color: colors.muted }]}>
                      {formatPrice(m.spentTotal)} / {formatPrice(m.maxTotalBudget)}
                    </Text>
                  </View>
                )}
              </AnimatedPressable>
            );
          })
        )}

        {/* Recent Deals */}
        <Text style={[styles.sectionTitle, { color: colors.text, marginTop: 24 }]}>Recent Deals</Text>

        {deals.length === 0 ? (
          <View style={[styles.emptyCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Ionicons name="pricetag-outline" size={32} color={colors.muted} />
            <Text style={[styles.emptyTitle, { color: colors.text }]}>No deals yet</Text>
            <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
              Deals will appear here as your agent scans marketplaces.
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
                  accessibilityLabel={`Deal: ${deal.listingTitle}`}
                >
                  <View style={styles.dealLeft}>
                    <Text style={[styles.dealTitle, { color: colors.text }]} numberOfLines={1}>
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
  headerSubtitle: { fontSize: 12, marginTop: 2 },
  createBtn: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    gap: 4,
  },
  createBtnText: { color: "#fff", fontWeight: "700", fontSize: 14 },

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
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  mandateName: { fontSize: 15, fontWeight: "700", flex: 1, marginRight: 8 },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  statusText: { fontSize: 11, fontWeight: "700", textTransform: "uppercase" },
  mandateQuery: { fontSize: 13, marginBottom: 10 },
  mandateStats: { flexDirection: "row", gap: 16 },
  statItem: { alignItems: "center" },
  statValue: { fontSize: 16, fontWeight: "800" },
  statLabel: { fontSize: 11, fontWeight: "600" },

  budgetBar: { marginTop: 10 },
  budgetTrack: { height: 4, borderRadius: 2, overflow: "hidden" },
  budgetFill: { height: "100%", borderRadius: 2 },
  budgetText: { fontSize: 11, marginTop: 4 },

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
    justifyContent: "space-between",
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderTopWidth: 1,
  },
  dealRowFirst: { borderTopWidth: 0 },
  dealLeft: { flex: 1, paddingRight: 12 },
  dealTitle: { fontSize: 14, fontWeight: "600" },
  dealMeta: { flexDirection: "row", gap: 8, marginTop: 2 },
  dealSource: { fontSize: 12, fontWeight: "500" },
  dealDiscount: { fontSize: 12, fontWeight: "700" },
  dealRight: { alignItems: "flex-end" },
  dealPrice: { fontSize: 14, fontWeight: "800" },
  dealRightRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 2 },
  dealBadge: { paddingHorizontal: 6, paddingVertical: 1, borderRadius: 4 },
  dealBadgeText: { fontSize: 10, fontWeight: "700" },
  quickBuyBtn: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
});
