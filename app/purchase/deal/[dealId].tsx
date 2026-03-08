/**
 * Deal Detail screen — shows full deal info with scoring breakdown.
 *
 * Actions: "Buy It" (opens affiliate URL), "I Got It" (confirms purchase),
 * "Not Interested" (declines deal).
 */

import React, { useEffect, useState, useCallback } from "react";
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Linking,
  Platform,
  Image,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter, useLocalSearchParams } from "expo-router";
import { useAppTheme } from "@/hooks/useAppTheme";
import { useSettings } from "@/lib/settings";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { formatPrice } from "@/lib/format";
import { collectorsApi } from "@/api/collectorsApi";
import { useToast } from "@/components/Toast";
import type { MandateDeal } from "@/data/types";

export default function DealDetailScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Deal Detail">
      <DealDetailScreen />
    </ScreenErrorBoundary>
  );
}

function DealDetailScreen() {
  const router = useRouter();
  const { dealId } = useLocalSearchParams<{ dealId: string }>();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();

  const [deal, setDeal] = useState<MandateDeal | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!dealId) return;
    let cancelled = false;
    (async () => {
      try {
        const d = await collectorsApi.getDeal(dealId) as MandateDeal;
        if (!cancelled) setDeal(d);
      } catch {
        if (!cancelled) showToast({ message: "Failed to load deal", type: "error" });
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [dealId]);

  const handleBuyIt = useCallback(async () => {
    if (!deal) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });

    try {
      await collectorsApi.clickDeal(deal.id);
      const url = deal.affiliateUrl || deal.listingUrl;
      if (url) {
        await Linking.openURL(url);
      }
      setDeal((prev) => prev ? { ...prev, status: "clicked", affiliateClick: true } : prev);
    } catch {
      showToast({ message: "Failed to open link", type: "error" });
    }
  }, [deal, settings.hapticsEnabled]);

  const handleConfirm = useCallback(async () => {
    if (!deal) return;
    setConfirming(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });

    try {
      await collectorsApi.confirmDeal(deal.id, deal.listingPrice);
      setDeal((prev) => prev ? { ...prev, status: "purchased" } : prev);
      showToast({ message: "Purchase confirmed!", type: "success" });
    } catch {
      showToast({ message: "Failed to confirm", type: "error" });
    } finally {
      setConfirming(false);
    }
  }, [deal, settings.hapticsEnabled]);

  const handleDecline = useCallback(async () => {
    if (!deal) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });

    try {
      await collectorsApi.declineDeal(deal.id);
      setDeal((prev) => prev ? { ...prev, status: "declined" } : prev);
      showToast({ message: "Deal dismissed", type: "success" });
    } catch {
      showToast({ message: "Failed to dismiss", type: "error" });
    }
  }, [deal, settings.hapticsEnabled]);

  // Guard: invalid or missing dealId
  if (!dealId) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={["left", "right"]}>
        <View style={styles.loadingWrap}>
          <Ionicons name="alert-circle-outline" size={40} color={colors.danger} />
          <Text style={[styles.errorText, { color: colors.text }]}>Invalid deal link</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={["left", "right"]}>
        <View style={styles.loadingWrap}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  if (!deal) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={["left", "right"]}>
        <View style={styles.loadingWrap}>
          <Ionicons name="alert-circle-outline" size={40} color={colors.danger} />
          <Text style={[styles.errorText, { color: colors.text }]}>Deal not found</Text>
        </View>
      </SafeAreaView>
    );
  }

  const hasDiscount = deal.priceVsQ50Pct != null && deal.priceVsQ50Pct < 0;
  const isPurchased = deal.status === "purchased";
  const isDeclined = deal.status === "declined";
  const isExpired = deal.status === "expired";
  const isActionable = !isPurchased && !isDeclined && !isExpired;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={["left", "right"]}>
      <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>

        {/* Listing Image */}
        {deal.listingImageUrl ? (
          <Image
            source={{ uri: deal.listingImageUrl }}
            style={[styles.image, { backgroundColor: colors.card }]}
            resizeMode="contain"
          />
        ) : (
          <View style={[styles.imagePlaceholder, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Ionicons name="image-outline" size={40} color={colors.muted} />
          </View>
        )}

        {/* Title + Source */}
        <Text style={[styles.dealTitle, { color: colors.text }]}>{deal.listingTitle}</Text>
        <View style={styles.metaRow}>
          <View style={[styles.sourceBadge, { backgroundColor: colors.accent + "15" }]}>
            <Text style={[styles.sourceText, { color: colors.accent }]}>{deal.listingSource}</Text>
          </View>
          {deal.listingSeller && (
            <Text style={[styles.sellerText, { color: colors.muted }]}>
              Seller: {deal.listingSeller}
            </Text>
          )}
          {deal.listingCondition && (
            <Text style={[styles.conditionText, { color: colors.muted }]}>
              {deal.listingCondition}
            </Text>
          )}
        </View>

        {/* Price */}
        <View style={[styles.priceCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <View style={styles.priceRow}>
            <Text style={[styles.priceLabel, { color: colors.muted }]}>Listing Price</Text>
            <Text style={[styles.priceValue, { color: colors.text }]}>
              {formatPrice(deal.listingPrice)}
            </Text>
          </View>
          {hasDiscount && (
            <View style={[styles.discountBadge, { backgroundColor: colors.success + "15" }]}>
              <Ionicons name="trending-down" size={14} color={colors.success} />
              <Text style={[styles.discountText, { color: colors.success }]}>
                {Math.abs(deal.priceVsQ50Pct!).toFixed(1)}% below market median
              </Text>
            </View>
          )}
        </View>

        {/* Price Analysis (if predictions available) */}
        {deal.predictedQ50 != null && (
          <View style={[styles.analysisCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[styles.cardTitle, { color: colors.text }]}>Price Analysis</Text>
            <View style={styles.predRow}>
              <PredBand label="Low (q10)" value={deal.predictedQ10} colors={colors} />
              <PredBand label="Median (q50)" value={deal.predictedQ50} colors={colors} highlight />
              <PredBand label="High (q90)" value={deal.predictedQ90} colors={colors} />
            </View>
            {/* Visual bar */}
            <View style={[styles.barTrack, { backgroundColor: colors.border }]}>
              <View style={[styles.barRange, { backgroundColor: colors.accent + "30", left: "10%", right: "10%" }]} />
              {deal.predictedQ50 != null && deal.predictedQ10 != null && deal.predictedQ90 != null && (
                <View
                  style={[
                    styles.barDot,
                    {
                      backgroundColor: hasDiscount ? colors.success : colors.warning,
                      left: `${Math.min(95, Math.max(5, ((deal.listingPrice - deal.predictedQ10) / (deal.predictedQ90 - deal.predictedQ10)) * 100))}%`,
                    },
                  ]}
                />
              )}
            </View>
            <Text style={[styles.barLabel, { color: colors.muted }]}>
              Listing price position within predicted range
            </Text>
          </View>
        )}

        {/* Provenance + Deal Score */}
        <View style={[styles.scoresCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <Text style={[styles.cardTitle, { color: colors.text }]}>Scoring</Text>
          <View style={styles.scoreRow}>
            <ScoreItem label="Provenance" value={deal.provenanceScore} colors={colors} />
            <ScoreItem label="Deal Score" value={deal.dealScore} colors={colors} />
          </View>
        </View>

        {/* Policy Checks */}
        {deal.policyReasons.length > 0 && (
          <View style={[styles.policyCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[styles.cardTitle, { color: colors.text }]}>Policy Checks</Text>
            {deal.policyReasons.map((reason, idx) => {
              const isFail = reason.startsWith("FAIL:");
              return (
                <View key={idx} style={styles.policyRow}>
                  <Ionicons
                    name={isFail ? "close-circle" : "checkmark-circle"}
                    size={16}
                    color={isFail ? colors.danger : colors.success}
                  />
                  <Text style={[styles.policyText, { color: colors.text }]}>{reason}</Text>
                </View>
              );
            })}
          </View>
        )}

        {/* Status badge */}
        {!isActionable && (
          <View style={[styles.statusCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Ionicons
              name={isPurchased ? "checkmark-circle" : isDeclined ? "close-circle" : "time"}
              size={24}
              color={isPurchased ? colors.success : isDeclined ? colors.muted : colors.danger}
            />
            <Text style={[styles.statusLabel, { color: colors.text }]}>
              {isPurchased ? "Purchased" : isDeclined ? "Declined" : "Expired"}
            </Text>
          </View>
        )}

        {/* Action Buttons */}
        {isActionable && (
          <View style={styles.actions}>
            <AnimatedPressable
              style={[styles.buyBtn, { backgroundColor: colors.accent }]}
              onPress={handleBuyIt}
              accessibilityRole="button"
              accessibilityLabel="Buy it"
            >
              <Ionicons name="open-outline" size={18} color="#fff" />
              <Text style={styles.buyBtnText}>Buy It</Text>
            </AnimatedPressable>

            {(deal.status === "clicked" || deal.affiliateClick) && (
              <AnimatedPressable
                style={[styles.confirmBtn, { backgroundColor: colors.success }]}
                onPress={handleConfirm}
                disabled={confirming}
                accessibilityRole="button"
                accessibilityLabel="I got it"
              >
                {confirming ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <>
                    <Ionicons name="checkmark" size={18} color="#fff" />
                    <Text style={styles.buyBtnText}>I Got It</Text>
                  </>
                )}
              </AnimatedPressable>
            )}

            <AnimatedPressable
              style={[styles.declineBtn, { borderColor: colors.border }]}
              onPress={handleDecline}
              accessibilityRole="button"
              accessibilityLabel="Not interested"
            >
              <Ionicons name="close" size={16} color={colors.muted} />
              <Text style={[styles.declineBtnText, { color: colors.muted }]}>Not Interested</Text>
            </AnimatedPressable>
          </View>
        )}

        <View style={{ height: Platform.OS === "ios" ? 40 : 24 }} />
      </ScrollView>
      <QuickNavBar />
    </SafeAreaView>
  );
}

function PredBand({ label, value, colors, highlight }: {
  label: string;
  value?: number | null;
  colors: Record<string, any>;
  highlight?: boolean;
}) {
  return (
    <View style={styles.predItem}>
      <Text style={[styles.predLabel, { color: colors.muted }]}>{label}</Text>
      <Text style={[styles.predValue, { color: colors.text }, highlight && { fontWeight: "800" }]}>
        {value != null ? formatPrice(value) : "—"}
      </Text>
    </View>
  );
}

function ScoreItem({ label, value, colors }: {
  label: string;
  value?: number | null;
  colors: Record<string, any>;
}) {
  const pct = value != null ? Math.round(value * 100) : 0;
  const barColor = pct >= 70 ? colors.success : pct >= 40 ? colors.warning : colors.danger;

  return (
    <View style={styles.scoreItem}>
      <Text style={[styles.scoreLabel, { color: colors.muted }]}>{label}</Text>
      <Text style={[styles.scoreValue, { color: colors.text }]}>
        {value != null ? value.toFixed(2) : "—"}
      </Text>
      <View style={[styles.scoreBar, { backgroundColor: colors.border }]}>
        <View style={[styles.scoreFill, { backgroundColor: barColor, width: `${pct}%` }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  container: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 24 },
  loadingWrap: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12 },
  errorText: { fontSize: 16, fontWeight: "600" },

  // Image
  image: { width: "100%", height: 200, borderRadius: 12, marginBottom: 12 },
  imagePlaceholder: {
    width: "100%",
    height: 160,
    borderRadius: 12,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 12,
  },

  // Title
  dealTitle: { fontSize: 18, fontWeight: "700", marginBottom: 8 },
  metaRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 16, alignItems: "center" },
  sourceBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  sourceText: { fontSize: 12, fontWeight: "700", textTransform: "uppercase" },
  sellerText: { fontSize: 12, fontWeight: "500" },
  conditionText: { fontSize: 12, fontWeight: "500" },

  // Price card
  priceCard: { borderWidth: 1, borderRadius: 12, padding: 14, marginBottom: 12 },
  priceRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  priceLabel: { fontSize: 13, fontWeight: "600" },
  priceValue: { fontSize: 24, fontWeight: "800" },
  discountBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    marginTop: 10,
    alignSelf: "flex-start",
  },
  discountText: { fontSize: 13, fontWeight: "700" },

  // Analysis card
  analysisCard: { borderWidth: 1, borderRadius: 12, padding: 14, marginBottom: 12 },
  cardTitle: { fontSize: 15, fontWeight: "700", marginBottom: 10 },
  predRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 12 },
  predItem: { alignItems: "center", flex: 1 },
  predLabel: { fontSize: 11, fontWeight: "600", marginBottom: 2 },
  predValue: { fontSize: 15, fontWeight: "700" },
  barTrack: { height: 8, borderRadius: 4, position: "relative", marginBottom: 6 },
  barRange: { position: "absolute", top: 0, bottom: 0, borderRadius: 4 },
  barDot: { position: "absolute", width: 12, height: 12, borderRadius: 6, top: -2 },
  barLabel: { fontSize: 10, textAlign: "center" },

  // Scores
  scoresCard: { borderWidth: 1, borderRadius: 12, padding: 14, marginBottom: 12 },
  scoreRow: { flexDirection: "row", gap: 16 },
  scoreItem: { flex: 1 },
  scoreLabel: { fontSize: 11, fontWeight: "600", marginBottom: 2 },
  scoreValue: { fontSize: 16, fontWeight: "800", marginBottom: 4 },
  scoreBar: { height: 4, borderRadius: 2, overflow: "hidden" },
  scoreFill: { height: "100%", borderRadius: 2 },

  // Policy
  policyCard: { borderWidth: 1, borderRadius: 12, padding: 14, marginBottom: 12 },
  policyRow: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 4 },
  policyText: { fontSize: 13, flex: 1 },

  // Status
  statusCard: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    justifyContent: "center",
  },
  statusLabel: { fontSize: 16, fontWeight: "700" },

  // Actions
  actions: { gap: 10, marginTop: 8 },
  buyBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 14,
    borderRadius: 10,
    gap: 6,
  },
  confirmBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 14,
    borderRadius: 10,
    gap: 6,
  },
  buyBtnText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  declineBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1,
    gap: 4,
  },
  declineBtnText: { fontSize: 14, fontWeight: "600" },
});
