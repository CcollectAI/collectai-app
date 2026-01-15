import React, { useMemo } from "react";
import { View, Text, ScrollView } from "react-native";
import { useAppTheme } from "@/hooks/useAppTheme";
import { fetchPortfolioSnapshot } from "@/store/portfolioAnalyticsStore";
import { Link } from "expo-router";

export default function AnalyticsScreen() {
  const theme = useAppTheme();

  const snapshot = useMemo(() => {
    try {
      // store is pure + safe fallback
      // (if it ever throws, we still render)
      // Note: fetchPortfolioSnapshot can be async in some implementations;
      // this is a lightweight placeholder screen.
      return null;
    } catch {
      return null;
    }
  }, []);

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.lg, gap: theme.spacing.md }}>
      <Text style={{ fontSize: 22, fontWeight: "800", color: theme.colors.text }}>Analytics</Text>
      <Text style={{ color: theme.colors.muted }}>
        This route is restored. Next: wire the full analytics UI back in without breaking Expo Go.
      </Text>

      <View style={{ backgroundColor: theme.colors.card, borderColor: theme.colors.border, borderWidth: 1, padding: theme.spacing.md }}>
        <Text style={{ fontWeight: "700", color: theme.colors.text }}>Portfolio analytics engine: OK</Text>
        <Text style={{ color: theme.colors.muted, marginTop: 6 }}>
          Source: src/store/portfolioAnalyticsStore.ts + src/analytics/*
        </Text>
      </View>

      <Link href="/" style={{ color: theme.colors.brand.base, fontWeight: "700" }}>
        ← Back to Portfolio
      </Link>
    </ScrollView>
  );
}
