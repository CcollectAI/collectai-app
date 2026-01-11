import React, { useEffect, useMemo, useState } from "react";
import { View, Text, ScrollView, Pressable, StyleSheet } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import Svg, { G, Path, Circle } from "react-native-svg";

/**
 * Pro Collector Analytics (Expo-Go safe)
 * - No extra chart libs; uses react-native-svg (already in Expo)
 * - Multiple pie charts + professional KPIs + concentration + movers
 * - Data: tries to read from collectorsClient.getPortfolioItems; falls back to mock
 */

// ---- Types ----
type PortfolioItem = {
  id: string;
  name: string;
  categoryId: string;
  categoryLabel?: string;
  value_eur: number;
  cost_eur?: number;
  change_7d_pct?: number;
  change_30d_pct?: number;
  liquidity?: "low" | "medium" | "high";
  condition?: "mint" | "nm" | "lp" | "mp" | "hp";
};

type RangeKey = "7D" | "30D" | "ALL";

// ---- Theme (match Items / Tiffany+Navy) ----
const THEME = {
  BG: "#E6FFFA",
  CARD: "#FFFFFF",
  BORDER: "rgba(12,34,51,0.10)",
  NAVY: "#0C2233",
  MUTED: "rgba(12,34,51,0.62)",
  ACCENT: "#38D6C7",
  ACCENT_SOFT: "rgba(56,214,199,0.18)",
  GREEN: "rgba(16,185,129,1)",
  RED: "rgba(239,68,68,1)",
};

// ---- Mock-safe data fallback ----
const MOCK_ITEMS: PortfolioItem[] = [
  { id: "i1", name: "Charizard Holo (PSA 9)", categoryId: "pokemon", categoryLabel: "Pokémon", value_eur: 1250, cost_eur: 800, change_7d_pct: 2.2, change_30d_pct: 6.4, liquidity: "high", condition: "mint" },
  { id: "i2", name: "Lorcana — Enchanted", categoryId: "lorcana", categoryLabel: "Lorcana", value_eur: 690, cost_eur: 520, change_7d_pct: -1.1, change_30d_pct: 3.1, liquidity: "medium", condition: "nm" },
  { id: "i3", name: "Gunpla — Limited RG", categoryId: "gunpla", categoryLabel: "Gunpla", value_eur: 240, cost_eur: 180, change_7d_pct: 0.4, change_30d_pct: 1.6, liquidity: "medium", condition: "nm" },
  { id: "i4", name: "Warhammer — OOP kit", categoryId: "warhammer", categoryLabel: "Warhammer", value_eur: 410, cost_eur: 250, change_7d_pct: 1.4, change_30d_pct: 4.0, liquidity: "low", condition: "lp" },
  { id: "i5", name: "MTG — Reserved List", categoryId: "mtg", categoryLabel: "MTG", value_eur: 980, cost_eur: 900, change_7d_pct: -0.6, change_30d_pct: 0.8, liquidity: "high", condition: "nm" },
  { id: "i6", name: "Designer Toy — Artist Drop", categoryId: "art-toys", categoryLabel: "Art Toys", value_eur: 540, cost_eur: 430, change_7d_pct: 3.6, change_30d_pct: 9.5, liquidity: "medium", condition: "mint" },
];

function fmtEUR(n: number) {
  const x = Math.round(n * 100) / 100;
  // keep stable formatting w/out Intl dependency issues
  const parts = x.toFixed(2).split(".");
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `€${parts.join(".")}`;
}

function clamp01(x: number) {
  return Math.max(0, Math.min(1, x));
}

function sum(nums: number[]) {
  return nums.reduce((a, b) => a + b, 0);
}

function pct(n: number) {
  const s = (Math.round(n * 10) / 10).toFixed(1);
  return `${s}%`;
}

// ---- Pie chart (react-native-svg) ----
type PieDatum = { label: string; value: number; color: string };

function polarToCartesian(cx: number, cy: number, r: number, angleRad: number) {
  return { x: cx + r * Math.cos(angleRad), y: cy + r * Math.sin(angleRad) };
}

function arcPath(cx: number, cy: number, r: number, start: number, end: number) {
  const startPt = polarToCartesian(cx, cy, r, start);
  const endPt = polarToCartesian(cx, cy, r, end);
  const large = end - start > Math.PI ? 1 : 0;
  return `M ${cx} ${cy} L ${startPt.x} ${startPt.y} A ${r} ${r} 0 ${large} 1 ${endPt.x} ${endPt.y} Z`;
}

function PieChart({
  data,
  size = 170,
  innerRatio = 0.62,
  title,
  subtitle,
}: {
  data: PieDatum[];
  size?: number;
  innerRatio?: number;
  title: string;
  subtitle?: string;
}) {
  const total = Math.max(1e-9, sum(data.map((d) => d.value)));
  const r = size / 2;
  const cx = r;
  const cy = r;

  let acc = -Math.PI / 2; // start top
  const slices = data.map((d) => {
    const angle = (d.value / total) * Math.PI * 2;
    const start = acc;
    const end = acc + angle;
    acc = end;
    return { ...d, start, end };
  });

  return (
    <View>
      <Text style={styles.chartTitle}>{title}</Text>
      {subtitle ? <Text style={styles.chartSub}>{subtitle}</Text> : null}

      <View style={{ marginTop: 10, alignItems: "center" }}>
        <Svg width={size} height={size}>
          <G>
            {slices.map((s, idx) => (
              <Path key={`${s.label}-${idx}`} d={arcPath(cx, cy, r, s.start, s.end)} fill={s.color} />
            ))}
            <Circle cx={cx} cy={cy} r={r * innerRatio} fill={THEME.CARD} />
          </G>
        </Svg>
      </View>

      <View style={{ marginTop: 10 }}>
        {data.slice(0, 6).map((d, i) => (
          <View key={`${d.label}-${i}`} style={styles.legendRow}>
            <View style={[styles.legendDot, { backgroundColor: d.color }]} />
            <Text style={styles.legendLabel} numberOfLines={1}>{d.label}</Text>
            <Text style={styles.legendValue}>{fmtEUR(d.value)}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

// ---- Screen ----
export default function AnalyticsScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [range, setRange] = useState<RangeKey>("30D");
  const [items, setItems] = useState<PortfolioItem[]>(MOCK_ITEMS);

  useEffect(() => {
    // Backend-ready: attempt to load from collectorsClient if present.
    // This is intentionally defensive to avoid bundler crashes.
    (async () => {
      try {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const mod = require("@/services/collectorsClient");
        const fn = mod?.getPortfolioItems;
        if (typeof fn === "function") {
          const data = await fn();
          if (Array.isArray(data) && data.length) setItems(data);
        }
      } catch {
        // keep mock
      }
    })();
  }, []);

  const totalValue = useMemo(() => sum(items.map((i) => i.value_eur || 0)), [items]);
  const totalCost = useMemo(() => sum(items.map((i) => i.cost_eur || 0)), [items]);

  const pnlAbs = totalValue - totalCost;
  const pnlPct = totalCost > 0 ? (pnlAbs / totalCost) * 100 : 0;

  const rangeKey = range === "7D" ? "change_7d_pct" : range === "30D" ? "change_30d_pct" : null;
  const weightedReturnPct = useMemo(() => {
    if (!rangeKey) return pnlPct; // fallback
    const w = sum(items.map((i) => i.value_eur || 0));
    if (w <= 0) return 0;
    const wr = sum(items.map((i) => (i.value_eur || 0) * ((i as any)[rangeKey] || 0))) / w;
    return wr;
  }, [items, rangeKey, pnlPct]);

  const categoryAgg = useMemo(() => {
    const map = new Map<string, { label: string; value: number; count: number }>();
    for (const it of items) {
      const k = it.categoryId || "other";
      const prev = map.get(k);
      const label = it.categoryLabel || k;
      if (!prev) map.set(k, { label, value: it.value_eur || 0, count: 1 });
      else map.set(k, { label, value: prev.value + (it.value_eur || 0), count: prev.count + 1 });
    }
    return [...map.entries()]
      .map(([id, v]) => ({ id, ...v }))
      .sort((a, b) => b.value - a.value);
  }, [items]);

  const topConcentration = useMemo(() => {
    const sorted = [...items].sort((a, b) => (b.value_eur || 0) - (a.value_eur || 0));
    const w = Math.max(1e-9, totalValue);
    const top1 = sorted[0] ? (sorted[0].value_eur || 0) / w : 0;
    const top5 = sum(sorted.slice(0, 5).map((i) => i.value_eur || 0)) / w;
    return { top1, top5 };
  }, [items, totalValue]);

  const liquidityAgg = useMemo(() => {
    const buckets: Record<string, number> = { high: 0, medium: 0, low: 0, unknown: 0 };
    for (const it of items) {
      const k = it.liquidity || "unknown";
      buckets[k] = (buckets[k] || 0) + (it.value_eur || 0);
    }
    return buckets;
  }, [items]);

  const movers = useMemo(() => {
    const key = rangeKey || "change_30d_pct";
    const sorted = [...items].sort((a, b) => ((b as any)[key] || 0) - ((a as any)[key] || 0));
    return {
      up: sorted.slice(0, 3),
      down: sorted.slice(-3).reverse(),
    };
  }, [items, rangeKey]);

  // deterministic palette
  const palette = [
    "rgba(56,214,199,1)",
    "rgba(12,34,51,0.92)",
    "rgba(99,102,241,0.95)",
    "rgba(245,158,11,0.95)",
    "rgba(236,72,153,0.92)",
    "rgba(34,197,94,0.90)",
    "rgba(239,68,68,0.90)",
  ];

  const categoryPie: PieDatum[] = useMemo(() => {
    return categoryAgg.slice(0, 6).map((c, idx) => ({
      label: `${c.label} (${c.count})`,
      value: c.value,
      color: palette[idx % palette.length],
    }));
  }, [categoryAgg]);

  const liquidityPie: PieDatum[] = useMemo(() => {
    const entries: { label: string; value: number; color: string }[] = [
      { label: "High liquidity", value: liquidityAgg.high, color: "rgba(34,197,94,0.90)" },
      { label: "Medium liquidity", value: liquidityAgg.medium, color: "rgba(245,158,11,0.92)" },
      { label: "Low liquidity", value: liquidityAgg.low, color: "rgba(239,68,68,0.90)" },
    ];
    const other = liquidityAgg.unknown || 0;
    if (other > 0) entries.push({ label: "Unknown", value: other, color: "rgba(12,34,51,0.45)" });
    return entries.filter((e) => e.value > 0.0001);
  }, [liquidityAgg]);

  const riskBand = useMemo(() => {
    // simple “risk score” proxy: concentration + low-liquidity share
    const lowShare = totalValue > 0 ? liquidityAgg.low / totalValue : 0;
    const score = clamp01(0.55 * topConcentration.top1 + 0.35 * lowShare + 0.10 * (topConcentration.top5 - topConcentration.top1));
    const label =
      score < 0.25 ? "Low" : score < 0.50 ? "Moderate" : score < 0.75 ? "High" : "Very High";
    return { score, label };
  }, [liquidityAgg.low, totalValue, topConcentration]);

  const deltaColor = weightedReturnPct >= 0 ? THEME.GREEN : THEME.RED;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: THEME.BG }]} edges={["top", "left", "right"]}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{
          paddingTop: Math.max(12, insets.top),
          paddingBottom: 28,
          paddingHorizontal: 16,
        }}
      >
        {/* Header */}
        <View style={styles.headerRow}>
          <Pressable onPress={() => router.back()} style={[styles.iconBtn, { borderColor: THEME.BORDER }]} accessibilityRole="button">
            <Ionicons name="chevron-back" size={18} color={THEME.NAVY} />
          </Pressable>

          <View style={{ flex: 1, paddingHorizontal: 10 }}>
            <Text style={[styles.hTitle, { color: THEME.NAVY }]} numberOfLines={1}>
              Portfolio Analytics
            </Text>
            <Text style={[styles.hSub, { color: THEME.MUTED }]} numberOfLines={1}>
              Allocation • risk • performance • movers
            </Text>
          </View>

          <Pressable onPress={() => {}} style={[styles.iconBtn, { borderColor: THEME.BORDER }]} accessibilityRole="button">
            <Ionicons name="download-outline" size={18} color={THEME.NAVY} />
          </Pressable>
        </View>

        {/* Range selector */}
        <View style={[styles.segment, { backgroundColor: THEME.CARD, borderColor: THEME.BORDER }]}>
          {(["7D", "30D", "ALL"] as RangeKey[]).map((k) => {
            const active = range === k;
            return (
              <Pressable
                key={k}
                onPress={() => setRange(k)}
                style={[styles.segmentBtn, active ? { backgroundColor: THEME.ACCENT_SOFT } : null]}
                accessibilityRole="button"
              >
                <Text style={[styles.segmentText, { color: THEME.NAVY }]}>{k}</Text>
              </Pressable>
            );
          })}
        </View>

        {/* KPI row */}
        <View style={styles.kpiRow}>
          <View style={[styles.kpiCard, { backgroundColor: THEME.CARD, borderColor: THEME.BORDER }]}>
            <Text style={[styles.kpiLabel, { color: THEME.MUTED }]}>Total value</Text>
            <Text style={[styles.kpiValue, { color: THEME.NAVY }]}>{fmtEUR(totalValue)}</Text>
          </View>

          <View style={[styles.kpiCard, { backgroundColor: THEME.CARD, borderColor: THEME.BORDER }]}>
            <Text style={[styles.kpiLabel, { color: THEME.MUTED }]}>Return ({range})</Text>
            <Text style={[styles.kpiValue, { color: deltaColor }]}>{pct(weightedReturnPct)}</Text>
          </View>
        </View>

        <View style={styles.kpiRow}>
          <View style={[styles.kpiCard, { backgroundColor: THEME.CARD, borderColor: THEME.BORDER }]}>
            <Text style={[styles.kpiLabel, { color: THEME.MUTED }]}>Unrealized P&L</Text>
            <Text style={[styles.kpiValue, { color: pnlAbs >= 0 ? THEME.GREEN : THEME.RED }]}>{fmtEUR(pnlAbs)}</Text>
            <Text style={[styles.kpiSub, { color: THEME.MUTED }]}>{pct(pnlPct)} vs cost</Text>
          </View>

          <View style={[styles.kpiCard, { backgroundColor: THEME.CARD, borderColor: THEME.BORDER }]}>
            <Text style={[styles.kpiLabel, { color: THEME.MUTED }]}>Risk band</Text>
            <Text style={[styles.kpiValue, { color: THEME.NAVY }]}>{riskBand.label}</Text>
            <Text style={[styles.kpiSub, { color: THEME.MUTED }]}>Score {Math.round(riskBand.score * 100)}/100</Text>
          </View>
        </View>

        {/* Charts */}
        <View style={[styles.card, { backgroundColor: THEME.CARD, borderColor: THEME.BORDER }]}>
          <PieChart
            title="Allocation by category"
            subtitle="Value-weighted exposure (top categories)"
            data={categoryPie}
            size={180}
            innerRatio={0.64}
          />
          <View style={styles.divider} />
          <View style={styles.metricRow}>
            <View style={styles.metric}>
              <Text style={[styles.metricLabel, { color: THEME.MUTED }]}>Top 1 holding</Text>
              <Text style={[styles.metricValue, { color: THEME.NAVY }]}>{pct(topConcentration.top1 * 100)}</Text>
            </View>
            <View style={styles.metric}>
              <Text style={[styles.metricLabel, { color: THEME.MUTED }]}>Top 5 concentration</Text>
              <Text style={[styles.metricValue, { color: THEME.NAVY }]}>{pct(topConcentration.top5 * 100)}</Text>
            </View>
          </View>
        </View>

        <View style={[styles.card, { backgroundColor: THEME.CARD, borderColor: THEME.BORDER }]}>
          <PieChart
            title="Liquidity mix"
            subtitle="A collector’s sellability view"
            data={liquidityPie}
            size={180}
            innerRatio={0.66}
          />
          <View style={styles.divider} />
          <Text style={[styles.note, { color: THEME.MUTED }]}>
            Tip: keep low-liquidity share controlled if you rely on fast exits, trade cycles, or liquidation events.
          </Text>
        </View>

        {/* Movers */}
        <View style={[styles.card, { backgroundColor: THEME.CARD, borderColor: THEME.BORDER }]}>
          <Text style={[styles.sectionTitle, { color: THEME.NAVY }]}>Top movers ({range})</Text>

          <View style={{ marginTop: 10 }}>
            <Text style={[styles.moverHeader, { color: THEME.MUTED }]}>Gainers</Text>
            {movers.up.map((m) => {
              const v = (m as any)[rangeKey || "change_30d_pct"] || 0;
              return (
                <View key={m.id} style={styles.moverRow}>
                  <Text style={[styles.moverName, { color: THEME.NAVY }]} numberOfLines={1}>{m.name}</Text>
                  <Text style={[styles.moverPct, { color: THEME.GREEN }]}>{pct(v)}</Text>
                </View>
              );
            })}
          </View>

          <View style={{ marginTop: 12 }}>
            <Text style={[styles.moverHeader, { color: THEME.MUTED }]}>Decliners</Text>
            {movers.down.map((m) => {
              const v = (m as any)[rangeKey || "change_30d_pct"] || 0;
              return (
                <View key={m.id} style={styles.moverRow}>
                  <Text style={[styles.moverName, { color: THEME.NAVY }]} numberOfLines={1}>{m.name}</Text>
                  <Text style={[styles.moverPct, { color: THEME.RED }]}>{pct(v)}</Text>
                </View>
              );
            })}
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({

  // --- Typography (match Items tab baseline) ---
  h1: { fontSize: 18, fontWeight: "900" },
  h2: { fontSize: 14, fontWeight: "900" },
  body: { fontSize: 12, fontWeight: "600", lineHeight: 17 },
  meta: { fontSize: 11, fontWeight: "600" },
safe: { flex: 1,
    backgroundColor: "#F2F4F7"
  },

  headerRow: { flexDirection: "row", alignItems: "center", marginBottom: 12 },
  iconBtn: {
    width: 36,
    height: 36,
    borderRadius: 999,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#fff",
  },
  hTitle: { fontSize: 16, fontWeight: "900" },
  hSub: { marginTop: 2, fontSize: 12, fontWeight: "700" },

  segment: { flexDirection: "row", borderWidth: 1, borderRadius: 14, padding: 4, marginBottom: 10 },
  segmentBtn: { flex: 1, paddingVertical: 10, borderRadius: 12, alignItems: "center" },
  segmentText: { fontSize: 12, fontWeight: "900" },

  kpiRow: { flexDirection: "row", gap: 10, marginBottom: 10 },
  kpiCard: { flex: 1, borderWidth: 1, borderRadius: 16, padding: 12 },
  kpiLabel: { fontSize: 11, fontWeight: "800" },
  kpiValue: { marginTop: 6, fontSize: 16, fontWeight: "900" },
  kpiSub: { marginTop: 4, fontSize: 11, fontWeight: "700" },

  card: { borderWidth: 1, borderRadius: 16, padding: 12, marginBottom: 10 },

  chartTitle: { fontSize: 13, fontWeight: "900", color: THEME.NAVY },
  chartSub: { marginTop: 2, fontSize: 11, fontWeight: "700", color: THEME.MUTED },

  legendRow: { flexDirection: "row", alignItems: "center", marginTop: 8 },
  legendDot: { width: 10, height: 10, borderRadius: 999, marginRight: 8 },
  legendLabel: { flex: 1, fontSize: 12, fontWeight: "800", color: THEME.NAVY },
  legendValue: { fontSize: 12, fontWeight: "900", color: THEME.NAVY },

  divider: { height: 1, backgroundColor: THEME.BORDER, marginVertical: 12 },

  metricRow: { flexDirection: "row", gap: 10 },
  metric: { flex: 1 },
  metricLabel: { fontSize: 11, fontWeight: "800" },
  metricValue: { marginTop: 6, fontSize: 14, fontWeight: "900" },

  note: { fontSize: 12, fontWeight: "700", lineHeight: 18 },
  sectionTitle: { fontSize: 14, fontWeight: "900" },
  moverHeader: { fontSize: 11, fontWeight: "900" },
  moverRow: { flexDirection: "row", alignItems: "center", marginTop: 8 },
  moverName: { flex: 1, fontSize: 12, fontWeight: "800" },
  moverPct: { fontSize: 12, fontWeight: "900" },
});
