/**
 * Portfolio total value display with animated counter and delta.
 *
 * Shows the collection value, change amount, and change percentage
 * with up/down colouring. Extracted from app/(tabs)/index.tsx.
 */
import React from "react";
import { View, Text, StyleSheet, type TextStyle } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedCounter } from "@/motion";
import type { Currency } from "@/lib/settings";
import { useAppTheme } from "@/hooks/useAppTheme";
import { useTranslation } from 'react-i18next';

// ── Props ──────────────────────────────────────────────────────────────

const TIER_COLORS: Record<string, string> = {
  Diamond: "#A78BFA",
  Gold: "#FBBF24",
  Silver: "#94A3B8",
  Unranked: "#64748B",
};

const TIER_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  Diamond: "diamond-outline",
  Gold: "trophy-outline",
  Silver: "medal-outline",
  Unranked: "help-circle-outline",
};

interface PortfolioValueHeaderProps {
  theme: {
    text: string;
    muted: string;
  };
  /**
   * The collection's value, or `null` when it is NOT YET KNOWN — still loading,
   * or the fetch failed.
   *
   * Nullable for the same reason the chart carries `loadFailed`: the total is
   * derived from `series`, so an empty series rendered a confident
   * **"COLLECTION VALUE €0  +€0 (0.00%)"** to a member holding €1.348 of items
   * (seen on Android 2026-09-09, for over a minute on a cold start). Zero is a
   * real answer; "we could not ask" is not zero. Matches `formatPrice`, which
   * already renders `—` for null.
   */
  total: number | null;
  delta: number;
  deltaPct: number;
  currency: Currency;
  formatPrice: (amount: number, currency?: Currency) => string;
  animationsEnabled?: boolean;
  tier?: string | null;
}

// ── Helpers ────────────────────────────────────────────────────────────

function formatPct(p?: number): string {
  if (p === undefined || p === null || Number.isNaN(p)) return "—";
  const sign = p > 0 ? "+" : "";
  return `${sign}${(p * 100).toFixed(2)}%`;
}

function formatDelta(n: number, currency: Currency, fp: PortfolioValueHeaderProps["formatPrice"]): string {
  // The sign leads, always. Handing a negative straight to `formatPrice` put it
  // between the symbol and the digits — "€-10" — while a gain read "+€10" two
  // characters away. Format the magnitude and prefix the sign ourselves.
  // ASCII hyphen, not U+2212: the percentage beside it comes from `toFixed`,
  // which emits a hyphen, and two different minus glyphs on one line show.
  const sign = n >= 0 ? "+" : "-";
  return `${sign}${fp(Math.abs(n), currency)}`;
}

// ── Component ──────────────────────────────────────────────────────────

function PortfolioValueHeaderInner({
  theme,
  total,
  delta,
  deltaPct,
  currency,
  formatPrice: fp,
  animationsEnabled = true,
  tier,
}: PortfolioValueHeaderProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const isPositive = deltaPct >= 0;
  const tierColor = tier ? TIER_COLORS[tier] ?? TIER_COLORS.Unranked : null;
  const tierIcon = tier ? TIER_ICONS[tier] ?? TIER_ICONS.Unranked : null;

  return (
    <View style={s.container}>
      <View style={s.labelRow}>
        <Text style={[s.label, { color: theme.muted }]}>COLLECTION VALUE</Text>
        {tier && tier !== 'Unranked' && tierColor && tierIcon && (
          <View style={[s.tierBadge, { backgroundColor: tierColor + '20' }]}>
            <Ionicons name={tierIcon} size={12} color={tierColor} />
            <Text style={[s.tierText, { color: tierColor }]}>{tier}</Text>
          </View>
        )}
      </View>
      {total === null ? (
        // Unknown, not zero. The delta line goes with it: "+€0 (0.00%)" beside
        // a dash would state a change we cannot compute either.
        <Text
          style={[s.totalValue, { color: theme.muted }]}
          accessibilityRole="text"
          accessibilityLabel={t('home.collection_value_unavailable_a11y', { defaultValue: 'Collection value: not available yet' })}
        >
          —
        </Text>
      ) : (
        <>
          <AnimatedCounter
            value={total}
            format={(v) => fp(v)}
            style={[s.totalValue, { color: theme.text }] as unknown as TextStyle}
            enabled={animationsEnabled}
            accessibilityLabel={`Collection value: ${fp(total)}`}
          />
          <Text
            style={[s.deltaText, { color: isPositive ? colors.success : colors.danger }]}
            accessibilityRole="text"
            accessibilityLabel={`Change: ${formatDelta(delta, currency, fp)}, ${formatPct(deltaPct)}`}
          >
            {formatDelta(delta, currency, fp)} ({formatPct(deltaPct)})
          </Text>
        </>
      )}
    </View>
  );
}

export const PortfolioValueHeader = React.memo(PortfolioValueHeaderInner);

// ── Styles ─────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  container: {
    marginBottom: 16,
  },
  label: {
    fontSize: 12,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  totalValue: {
    fontSize: 36,
    fontWeight: "800",
    letterSpacing: -0.5,
  },
  deltaText: {
    fontSize: 15,
    fontWeight: "700",
    marginTop: 4,
  },
  labelRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 4,
  },
  tierBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
  },
  tierText: {
    fontSize: 11,
    fontWeight: "700",
  },
});
