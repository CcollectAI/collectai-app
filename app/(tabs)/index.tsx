import React, { useEffect, useMemo, useState } from "react";
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
import Svg, { Polyline, Line } from "react-native-svg";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { dataProvider, type PortfolioSummary, type Item as DataItem } from "@/data";
import { InboxHeaderButton } from "@/components/InboxHeaderButton";
import { AnimatedPressable, useEnterReveal } from "@/motion";

type RangeKey = "1D" | "7D" | "30D";

type PortfolioPoint = { t: number; v: number };

type ItemRow = {
  id: string;
  name: string;
  category?: string;
  value: number;
  changePct?: number;
};

function formatMoneyEUR(n: number) {
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

function formatPct(p?: number) {
  if (p === undefined || p === null || Number.isNaN(p)) return "—";
  const sign = p > 0 ? "+" : "";
  return `${sign}${(p * 100).toFixed(2)}%`;
}

function clamp01(x: number) {
  return Math.max(0, Math.min(1, x));
}

function normalizeSeries(points: PortfolioPoint[]) {
  if (!points.length) return [];
  const vals = points.map((p) => p.v);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  return points.map((p) => ({ ...p, nv: (p.v - min) / span }));
}

function extractSeries(raw: any): PortfolioPoint[] {
  // Accept a bunch of plausible shapes:
  // - [{t,v}]
  // - [{x,y}]
  // - { points: [...] }
  // - { series: [...] }
  const arr =
    (Array.isArray(raw) && raw) ||
    raw?.points ||
    raw?.series ||
    raw?.data ||
    [];
  if (!Array.isArray(arr)) return [];
  return arr
    .map((p: any, idx: number) => {
      const t = typeof p?.t === "number" ? p.t : typeof p?.x === "number" ? p.x : idx;
      const v = typeof p?.v === "number" ? p.v : typeof p?.y === "number" ? p.y : Number(p?.value);
      if (typeof v !== "number" || Number.isNaN(v)) return null;
      return { t, v };
    })
    .filter(Boolean) as PortfolioPoint[];
}

function extractItems(raw: any): ItemRow[] {
  // Accept:
  // - raw.items
  // - raw.holdings / raw.positions
  // - raw.snapshot.items, etc.
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
          : typeof it?.pctChange === "number"
          ? it.pctChange
          : typeof it?.change === "number"
          ? it.change
          : undefined;

      const category = it?.category ? String(it.category) : undefined;

      if (!Number.isFinite(value)) return null;
      return { id, name, category, value, changePct };
    })
    .filter(Boolean) as ItemRow[];
}

export default function PortfolioScreen() {
  const [range, setRange] = useState<RangeKey>("7D");
  const [series, setSeries] = useState<PortfolioPoint[]>([]);
  const [items, setItems] = useState<ItemRow[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  // Fallback chart series (chart data not yet in DataProvider)
  const fallbackSeries: PortfolioPoint[] = useMemo(() => [
    { t: 0, v: 12400 },
    { t: 1, v: 12340 },
    { t: 2, v: 12510 },
    { t: 3, v: 12680 },
    { t: 4, v: 12590 },
    { t: 5, v: 12840 },
    { t: 6, v: 13120 },
    { t: 7, v: 13040 },
    { t: 8, v: 13310 },
    { t: 9, v: 13480 },
    { t: 10, v: 13290 },
    { t: 11, v: 13610 },
  ], []);

  const loadData = async () => {
    setLoading(true);
    setError(null);

    try {
      // Fetch from DataProvider (mock or real based on EXPO_PUBLIC_SUPABASE_MODE)
      const [summary, dataItems] = await Promise.all([
        dataProvider.getPortfolioSummary(),
        dataProvider.listItems(),
      ]);

      // Map DataProvider items to screen ItemRow shape
      const mappedItems: ItemRow[] = dataItems.map((item: DataItem) => ({
        id: item.id,
        name: item.name,
        category: item.category,
        value: item.price,
        changePct: undefined, // Not available in DataProvider yet
      }));

      // Sort by value descending
      const sorted = mappedItems.sort((a, b) => b.value - a.value);

      setTotal(summary.total);
      setItems(sorted);
      setSeries(fallbackSeries); // Chart series uses fallback for now
    } catch (e: any) {
      console.warn("[PortfolioScreen] loadData error:", e);
      setError(e?.message || "Failed to load portfolio data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [range]);

  const chart = useMemo(() => {
    const pts = normalizeSeries(series);
    return pts;
  }, [series]);

  // Chart geometry
  const W = 320; // virtual width (scaled by viewBox)
  const H = 170; // visible height (this is the "make it visible" fix)
  const PAD_X = 10;
  const PAD_Y = 14;

  const polylinePoints = useMemo(() => {
    if (!chart.length) return "";
    const n = chart.length;
    return chart
      .map((p: any, i: number) => {
        const x = PAD_X + (i * (W - PAD_X * 2)) / Math.max(1, n - 1);
        const y = PAD_Y + (1 - clamp01(p.nv)) * (H - PAD_Y * 2);
        return `${x},${y}`;
      })
      .join(" ");
  }, [chart]);

  const rangeButtons: RangeKey[] = ["1D", "7D", "30D"];

  // Loading state
  if (loading) {
    return (
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={stylesVars.tiffany} />
          <Text style={styles.loadingText}>Loading portfolio...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Error state
  if (error) {
    return (
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
        <View style={styles.centerContainer}>
          <Ionicons name="alert-circle-outline" size={48} color={stylesVars.error} />
          <Text style={styles.errorText}>{error}</Text>
          <AnimatedPressable style={styles.retryBtn} onPress={loadData}>
            <Text style={styles.retryText}>Retry</Text>
          </AnimatedPressable>
        </View>
      </SafeAreaView>
    );
  }

  // Empty state
  if (items.length === 0 && total === 0) {
    return (
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
        <View style={styles.centerContainer}>
          <Ionicons name="albums-outline" size={48} color={stylesVars.sub} />
          <Text style={styles.emptyText}>No items in your collection yet</Text>
          <Text style={styles.emptySubtext}>Add items to start tracking your portfolio</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
      <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
        <Animated.View style={animatedStyle}>
        {/* Header */}
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.kicker}>Collection Value</Text>
            <Text style={styles.total}>{formatMoneyEUR(total)}</Text>
          </View>

          <View style={styles.headerActions}>
            <InboxHeaderButton size={20} />
            <AnimatedPressable
              accessibilityRole="button"
              style={styles.settingsBtn}
              onPress={() => {
                // Keep this non-destructive; wire later.
                // You can route to settings if you already have it.
              }}
            >
              <Ionicons name="settings-outline" size={20} color={stylesVars.navy} />
            </AnimatedPressable>
          </View>
        </View>

        {/* Range toggles */}
        <View style={styles.rangeRow}>
          {rangeButtons.map((k) => {
            const active = k === range;
            return (
              <AnimatedPressable
                key={k}
                accessibilityRole="button"
                onPress={() => setRange(k)}
                style={[styles.rangeBtn, active ? styles.rangeBtnActive : null]}
              >
                <Text style={[styles.rangeText, active ? styles.rangeTextActive : null]}>{k}</Text>
              </AnimatedPressable>
            );
          })}
        </View>

        {/* Chart card */}
        <View style={styles.card}>
          <Svg
            width="100%"
            height={H}
            viewBox={`0 0 ${W} ${H}`}
            preserveAspectRatio="none"
          >
            {/* gridlines */}
            <Line x1={0} y1={H / 2} x2={W} y2={H / 2} stroke={stylesVars.grid} strokeWidth={1} />
            <Line x1={0} y1={PAD_Y} x2={W} y2={PAD_Y} stroke={stylesVars.grid} strokeWidth={1} />
            <Line x1={0} y1={H - PAD_Y} x2={W} y2={H - PAD_Y} stroke={stylesVars.grid} strokeWidth={1} />

            {/* series */}
            <Polyline
              points={polylinePoints}
              fill="none"
              stroke={stylesVars.tiffany}
              strokeWidth={3}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          </Svg>

          <View style={styles.chartFooter}>
            <Ionicons name="trending-up-outline" size={16} color={stylesVars.navy} />
            <Text style={styles.chartHint}>Value trend (demo/analytics-driven)</Text>
          </View>
        </View>

        {/* Analytics CTA - matches QuickScan ingress style */}
        <AnimatedPressable
          style={styles.analyticsCta}
          onPress={() => router.push("/analytics")}
        >
          <View style={styles.analyticsIconCircle}>
            <Ionicons name="bar-chart-outline" size={32} color={stylesVars.tiffany} />
          </View>
          <Text style={styles.analyticsTitle}>Analytics</Text>
          <Text style={styles.analyticsSubtitle}>
            View detailed insights, trends, and portfolio performance metrics.
          </Text>
          <View style={styles.analyticsButton}>
            <Text style={styles.analyticsButtonText}>View Analytics</Text>
            <Ionicons name="chevron-forward" size={18} color={stylesVars.tiffany} />
          </View>
        </AnimatedPressable>

        {/* List header */}
        <View style={styles.sectionRow}>
          <Text style={styles.sectionTitle}>Collection</Text>
          <Text style={styles.sectionRight}>{items.length ? `${items.length} items` : ""}</Text>
        </View>

        {/* Value-ranked list */}
        <View style={styles.listCard}>
          {items.slice(0, 12).map((it, idx) => {
            const isUp = (it.changePct ?? 0) >= 0;
            return (
              <View key={it.id} style={[styles.row, idx === 0 ? styles.rowFirst : null]}>
                <View style={styles.rowLeft}>
                  <Text style={styles.rowName} numberOfLines={1}>{it.name}</Text>
                  <Text style={styles.rowSub} numberOfLines={1}>
                    {it.category ? it.category : "—"} • {formatPct(it.changePct)}
                  </Text>
                </View>

                <View style={styles.rowRight}>
                  <Text style={styles.rowValue}>{formatMoneyEUR(it.value)}</Text>
                  <Text style={[styles.rowPct, isUp ? styles.pctUp : styles.pctDown]}>
                    {formatPct(it.changePct)}
                  </Text>
                </View>
              </View>
            );
          })}
        </View>

        <View style={{ height: Platform.OS === "ios" ? 24 : 18 }} />
        </Animated.View>
      </ScrollView>
    </SafeAreaView>
  );
}

const stylesVars = {
  tiffany: "#38D6C7",
  tiffanySoft: "#E9FFFC",
  navy: "#0B1B3A",
  card: "#FFFFFF",
  bg: "#EAFBFF",
  sub: "#5B6B86",
  grid: "rgba(11,27,58,0.10)",
  border: "rgba(11,27,58,0.08)",
  error: "#B42318",
  success: "#0A7D4E",
};

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: stylesVars.bg },
  container: { paddingHorizontal: 16, paddingTop: 10, paddingBottom: 22 },

  // Loading/Error/Empty states
  centerContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 24,
  },
  loadingText: {
    marginTop: 12,
    color: stylesVars.sub,
    fontSize: 14,
    fontWeight: "600",
  },
  errorText: {
    marginTop: 12,
    color: stylesVars.error,
    fontSize: 14,
    fontWeight: "600",
    textAlign: "center",
  },
  retryBtn: {
    marginTop: 16,
    paddingVertical: 10,
    paddingHorizontal: 20,
    backgroundColor: stylesVars.tiffany,
    borderRadius: 6,
  },
  retryText: {
    color: stylesVars.card,
    fontWeight: "700",
    fontSize: 14,
  },
  emptyText: {
    marginTop: 12,
    color: stylesVars.navy,
    fontSize: 16,
    fontWeight: "700",
    textAlign: "center",
  },
  emptySubtext: {
    marginTop: 6,
    color: stylesVars.sub,
    fontSize: 13,
    textAlign: "center",
  },

  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 10,
  },
  headerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  kicker: { color: stylesVars.sub, fontSize: 13, marginBottom: 4 },
  total: { color: stylesVars.navy, fontSize: 32, fontWeight: "800" },
  settingsBtn: {
    width: 40,
    height: 40,
    backgroundColor: stylesVars.card,
    borderWidth: 1,
    borderColor: stylesVars.border,
    alignItems: "center",
    justifyContent: "center",
  },

  rangeRow: { flexDirection: "row", gap: 10, marginBottom: 10 },
  rangeBtn: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: stylesVars.card,
    borderWidth: 1,
    borderColor: stylesVars.border,
  },
  rangeBtnActive: { backgroundColor: stylesVars.tiffanySoft, borderColor: "rgba(56,214,199,0.35)" },
  rangeText: { color: stylesVars.sub, fontWeight: "700" },
  rangeTextActive: { color: stylesVars.navy },

  card: {
    backgroundColor: stylesVars.card,
    borderWidth: 1,
    borderColor: stylesVars.border,
    padding: 12,
    marginBottom: 14,
  },
  chartFooter: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 10 },
  chartHint: { color: stylesVars.sub, fontSize: 12, fontWeight: "600" },

  // Analytics CTA - matches QuickScan ingress card style
  analyticsCta: {
    borderRadius: 16,
    padding: 20,
    backgroundColor: stylesVars.card,
    marginBottom: 14,
    elevation: 2,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
  },
  analyticsIconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 12,
    backgroundColor: stylesVars.tiffanySoft,
  },
  analyticsTitle: {
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 6,
    color: stylesVars.navy,
  },
  analyticsSubtitle: {
    fontSize: 14,
    opacity: 0.75,
    marginBottom: 16,
    color: stylesVars.sub,
  },
  analyticsButton: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: stylesVars.tiffanySoft,
  },
  analyticsButtonText: {
    fontSize: 14,
    fontWeight: "600",
    marginRight: 4,
    color: stylesVars.tiffany,
  },

  sectionRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginTop: 6,
    marginBottom: 10,
  },
  sectionTitle: { fontSize: 16, fontWeight: "800", color: stylesVars.navy },
  sectionRight: { fontSize: 12, fontWeight: "700", color: stylesVars.sub },

  listCard: {
    backgroundColor: stylesVars.card,
    borderWidth: 1,
    borderColor: stylesVars.border,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderTopWidth: 1,
    borderTopColor: stylesVars.border,
  },
  rowFirst: { borderTopWidth: 0 },
  rowLeft: { flex: 1, paddingRight: 10 },
  rowName: { color: stylesVars.navy, fontWeight: "800", fontSize: 14 },
  rowSub: { color: stylesVars.sub, fontWeight: "700", fontSize: 12, marginTop: 3 },
  rowRight: { alignItems: "flex-end", minWidth: 92 },
  rowValue: { color: stylesVars.navy, fontWeight: "800", fontSize: 14 },
  rowPct: { fontWeight: "900", fontSize: 12, marginTop: 3 },
  pctUp: { color: stylesVars.success },
  pctDown: { color: stylesVars.error },
});
