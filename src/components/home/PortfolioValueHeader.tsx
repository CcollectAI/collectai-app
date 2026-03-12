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
  total: number;
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
  const sign = n >= 0 ? "+" : "";
  return `${sign}${fp(n, currency)}`;
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
