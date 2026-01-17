import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, SafeAreaView, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import UserProfileSummaryCard from "@/components/UserProfileSummaryCard";
import { getPortfolioItems } from "@/services/collectorsClient";

/**
 * User Profile Screen
 * - Shows a portfolio summary card (event-card style)
 * - Includes "Request to Chat" button (hook it to your chat request function)
 */
export default function UserProfileScreen() {
  const params = useLocalSearchParams();
  const userId = String((params as any)?.userId ?? "me");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<any[]>([]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getPortfolioItems();
        if (!cancelled) setItems(Array.isArray(data) ? data : []);
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? "Failed to load portfolio");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true; // keep TS happy in some configs
    };
  }, []);

  const totals = useMemo(() => {
    const arr = Array.isArray(items) ? items : [];
    const values = arr
      .map((it) => {
        const v =
          it?.value ??
          it?.current_value ??
          it?.currentValue ??
          it?.price ??
          it?.market_value ??
          it?.marketValue;
        return typeof v === "number" && isFinite(v) ? v : 0;
      });

    const totalValue = values.reduce((a, b) => a + b, 0);
    const count = arr.length;

    // If an item has a dayChangePct, average-weight it lightly; otherwise null
    const dayPcts = arr
      .map((it) => it?.dayChangePct ?? it?.change24hPct ?? it?.pct_24h)
      .filter((x: any) => typeof x === "number" && isFinite(x));

    const dayChangePct = dayPcts.length ? (dayPcts.reduce((a: number, b: number) => a + b, 0) / dayPcts.length) : null;

    return { totalValue, count, dayChangePct };
  }, [items]);

  const requestToChat = () => {
    // TODO: connect this to your real "request to chat" action.
    // Example: requestChat({ userId })
    console.log("requestToChat:", { userId });
  };

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.pageTitle}>Profile</Text>

        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator />
            <Text style={styles.muted}>Loading…</Text>
          </View>
        ) : error ? (
          <View style={styles.center}>
            <Text style={styles.error}>{error}</Text>
          </View>
        ) : (
          <UserProfileSummaryCard
            title={userId === "me" ? "Your Collector Profile" : "Collector Profile"}
            subtitle={userId === "me" ? "Portfolio overview" : `User: ${userId}`}
            totalValueEur={totals.totalValue}
            itemsCount={totals.count}
            dayChangePct={totals.dayChangePct}
            onRequestChat={requestToChat}
          />
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#cfefff" }, // tiffany-ish background
  container: { padding: 14, gap: 12 },
  pageTitle: { color: "#0b1f3a", fontSize: 18, fontWeight: "900" },
  center: { padding: 14, alignItems: "center", gap: 8 },
  muted: { color: "#23405c", fontSize: 12, fontWeight: "700" },
  error: { color: "#b00020", fontSize: 12, fontWeight: "900" },
});
