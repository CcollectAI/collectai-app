/**
 * Portfolio total value display with animated counter and delta.
 *
 * Shows the collection value, change amount, and change percentage
 * with up/down colouring. Extracted from app/(tabs)/index.tsx.
 */
import React from "react";
import { View, Text, StyleSheet, type TextStyle } from "react-native";
import { AnimatedCounter } from "@/motion";
import type { Currency } from "@/lib/settings";

// ── Props ──────────────────────────────────────────────────────────────

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
}: PortfolioValueHeaderProps) {
  const isPositive = deltaPct >= 0;

  return (
    <View style={s.container}>
      <Text style={[s.label, { color: theme.muted }]}>COLLECTION VALUE</Text>
      <AnimatedCounter
        value={total}
        format={(v) => fp(v)}
        style={[s.totalValue, { color: theme.text }] as unknown as TextStyle}
        enabled={animationsEnabled}
        accessibilityLabel={`Collection value: ${fp(total)}`}
      />
      <Text
        style={[s.deltaText, { color: isPositive ? "#10B981" : "#EF4444" }]}
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
    marginBottom: 4,
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
});
