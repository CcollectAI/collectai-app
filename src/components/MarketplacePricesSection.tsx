/**
 * Marketplace prices section for item detail screen.
 *
 * Renders a collapsible "Market Prices" header with error state and retry,
 * market hit rows (title/source/price), and a "View all N results" link.
 *
 * Extracted from app/item/[id].tsx to reduce file size.
 */
import React from "react";
import {
  View,
  Text,
  Pressable,
  ActivityIndicator,
  Linking,
  StyleSheet,
} from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable } from "@/motion";
import logger from "@/utils/logger";

// ── Exported types ──────────────────────────────────────────────────────

export interface MarketHit {
  title: string;
  price: number;
  url?: string;
  affiliate_url?: string;
  source?: string;
  provider?: string;
  condition?: string;
}

// ── Props interface ─────────────────────────────────────────────────────

interface MarketplacePricesSectionProps {
  theme: {
    text: string;
    muted: string;
    accent: string;
    border: string;
    background: string;
    card: string;
  };
  marketResults: MarketHit[];
  marketLoading: boolean;
  marketExpanded: boolean;
  marketError: boolean;
  editableName: string;
  onToggleExpanded: () => void;
  onRetry: () => void;
  formatPrice: (value: number | undefined, currency?: string) => string;
  toNum: (value: string | number | undefined | null) => number | undefined;
}

// ── Component ───────────────────────────────────────────────────────────

export const MarketplacePricesSection = React.memo(function MarketplacePricesSection({
  theme,
  marketResults,
  marketLoading,
  marketExpanded,
  marketError,
  editableName,
  onToggleExpanded,
  onRetry,
  formatPrice,
  toNum,
}: MarketplacePricesSectionProps) {
  return (
    <View style={[s.sectionBlock, { borderTopColor: theme.border }]}>
      <Pressable
        onPress={onToggleExpanded}
        style={s.sectionHeaderRow}
        accessibilityRole="button"
        accessibilityLabel={`Market prices, ${marketExpanded ? 'expanded' : 'collapsed'}`}
      >
        <View style={s.sectionHeaderLeft}>
          <Ionicons name="cart-outline" size={20} color={theme.accent} />
          <Text style={[s.sectionTitle, { color: theme.text }]}>Market Prices</Text>
        </View>
        {marketLoading ? (
          <ActivityIndicator size="small" color={theme.accent} />
        ) : (
          <Ionicons
            name={marketExpanded ? "chevron-up" : "chevron-down"}
            size={18}
            color={theme.muted}
          />
        )}
      </Pressable>
      {marketExpanded && marketError && marketResults.length === 0 && !marketLoading && (
        <View style={s.sectionContent}>
          <Text style={[s.emptyText, { color: theme.muted }]}>
            Could not load market prices. Check your connection and try again.
          </Text>
          <AnimatedPressable
            onPress={onRetry}
            style={[s.retryBtn, { borderColor: theme.accent }]}
            accessibilityRole="button"
            accessibilityLabel="Retry loading market prices"
          >
            <Text style={{ color: theme.accent, fontSize: 13, fontWeight: "600" }}>Retry</Text>
          </AnimatedPressable>
        </View>
      )}
      {marketExpanded && marketResults.length > 0 && (
        <View style={s.sectionContent}>
          {marketResults.slice(0, 5).map((hit, idx) => (
            <Pressable
              key={idx}
              onPress={() => {
                const openUrl = hit.affiliate_url || hit.url;
                if (openUrl) Linking.openURL(openUrl).catch((err) => {
                  logger.warn("[ItemDetail] Failed to open URL", err);
                });
              }}
              style={[s.marketHitRow, { borderBottomColor: theme.border }]}
              accessibilityRole="link"
              accessibilityLabel={`${hit.title}, ${formatPrice(toNum(hit.price))} on ${hit.source || hit.provider || "marketplace"}`}
            >
              <View style={{ flex: 1 }}>
                <Text style={[s.marketHitTitle, { color: theme.text }]} numberOfLines={1}>
                  {hit.title}
                </Text>
                <Text style={[s.marketHitMeta, { color: theme.muted }]}>
                  {hit.source || hit.provider} {hit.condition ? `· ${hit.condition}` : ""}
                </Text>
              </View>
              <Text style={[s.marketHitPrice, { color: theme.text }]}>
                {formatPrice(toNum(hit.price))}
              </Text>
            </Pressable>
          ))}
          {marketResults.length > 5 && (
            <AnimatedPressable
              onPress={() => {
                // `/search`, and specifically NOT `/(tabs)/search`.
                //
                // This link has now had three targets, and the reason is the
                // same each time: it must land on a screen that RUNS a query
                // and READS `q`. The Market tab reads no params (a `q` sent
                // there was silently dropped); market-hub read `q` but was
                // deleted 2026-08-12 when the Market tab became the grid.
                //
                // The tab file `(tabs)/search.tsx` is a one-line re-export of
                // this same screen, so it would work at runtime — but
                // `npm run check:params` resolves a push target to its route
                // FILE, and that file has no `useLocalSearchParams` of its
                // own, so it would report "that route reads: (none)" and this
                // `?q=` contract would stop being checkable. `/search` reads it
                // at app/search.tsx:229 and stays a valid deep link.
                router.push({
                  pathname: "/search",
                  params: { q: editableName },
                });
              }}
              style={s.viewAllLink}
              accessibilityRole="link"
              accessibilityLabel={`View all ${marketResults.length} marketplace results`}
            >
              <Text style={[s.viewAllLinkText, { color: theme.accent }]}>
                View all {marketResults.length} results
              </Text>
              <Ionicons name="arrow-forward" size={14} color={theme.accent} />
            </AnimatedPressable>
          )}
        </View>
      )}
      {marketExpanded && marketResults.length === 0 && !marketLoading && !marketError && (
        <Text style={[s.emptyText, { color: theme.muted }]}>
          No listings found for this item.
        </Text>
      )}
    </View>
  );
});

// ── Styles ──────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  // Shared section layout (duplicated from parent — matches GradingSection pattern)
  sectionBlock: { marginTop: 16, paddingTop: 12, borderTopWidth: 1 },
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 4,
  },
  sectionHeaderLeft: { flexDirection: "row", alignItems: "center", gap: 8 },
  sectionTitle: { fontSize: 14, fontWeight: "600" },
  sectionContent: { marginTop: 10 },
  emptyText: {
    fontSize: 13,
    marginTop: 8,
    fontStyle: "italic",
  },
  retryBtn: {
    alignSelf: "flex-start",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    marginTop: 10,
  },
  marketHitRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 8,
  },
  marketHitTitle: {
    fontSize: 13,
    fontWeight: "500",
  },
  marketHitMeta: {
    fontSize: 11,
    marginTop: 2,
  },
  marketHitPrice: {
    fontSize: 14,
    fontWeight: "700",
    minWidth: 60,
    textAlign: "right",
  },
  viewAllLink: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    paddingVertical: 10,
    marginTop: 4,
  },
  viewAllLinkText: {
    fontSize: 13,
    fontWeight: "600",
  },
});
