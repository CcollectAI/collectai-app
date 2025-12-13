#!/usr/bin/env bash
set -euo pipefail

TARGET="app/(tabs)/index.tsx"

if [ ! -f "$TARGET" ]; then
  echo "ERROR: $TARGET not found. Aborting to avoid writing into the wrong router root."
  echo "Expected active router root is app/ (NOT src/app/)."
  exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
cp "$TARGET" "${TARGET}.bak_${TS}"

cat > "$TARGET" <<'TSX'
import React, { useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  Pressable,
  StyleSheet,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Polyline, Line } from "react-native-svg";
import { Ionicons } from "@expo/vector-icons";

// Keep imports conservative and optional.
// If these paths differ in your repo, the fallback data will still render.
let analyticsApi: any = null;
try {
  // Common paths from the thread summaries: analytics/store consolidated.
  // Adjust if your repo uses a different alias or location.
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  analyticsApi = require("@/src/store/portfolioAnalyticsStore");
} catch (_e) {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    analyticsApi = require("../src/store/portfolioAnalyticsStore");
  } catch (_e2) {
    analyticsApi = null;
  }
}

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

  useEffect(() => {
    let mounted = true;

    async function load() {
      // Fallback data must ALWAYS render (no blank chart).
      const fallbackSeries: PortfolioPoint[] = [
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
      ];

      const fallbackItems: ItemRow[] = [
        { id: "1", name: "PSA 10 Lugia (Neo Genesis)", category: "Pokémon", value: 3450, changePct: 0.028 },
        { id: "2", name: "Gunpla MG Barbatos (built)", category: "Gunpla", value: 1820, changePct: -0.011 },
        { id: "3", name: "Funko: Vaulted Grail", category: "Funko", value: 1250, changePct: 0.007 },
        { id: "4", name: "Warhammer Army Lot", category: "Warhammer", value: 980, changePct: 0.014 },
        { id: "5", name: "Designer Toy (limited run)", category: "Art Toys", value: 760, changePct: -0.006 },
      ];

      try {
        if (analyticsApi?.fetchPortfolioSeries) {
          const raw = await analyticsApi.fetchPortfolioSeries({ range });
          const s = extractSeries(raw);
          if (mounted) setSeries(s.length ? s : fallbackSeries);
        } else {
          if (mounted) setSeries(fallbackSeries);
        }

        // Snapshot: try to get value-ranked positions/items.
        if (analyticsApi?.fetchPortfolioSnapshot) {
          const snap = await analyticsApi.fetchPortfolioSnapshot();
          const extracted = extractItems(snap);
          const sorted = extracted.sort((a, b) => b.value - a.value);
          if (mounted) setItems(sorted.length ? sorted : fallbackItems);
          const computedTotal =
            typeof snap?.totalValue === "number"
              ? snap.totalValue
              : sorted.reduce((acc, it) => acc + it.value, 0);
          if (mounted) setTotal(computedTotal || fallbackItems.reduce((acc, it) => acc + it.value, 0));
        } else {
          if (mounted) {
            setItems(fallbackItems.slice().sort((a, b) => b.value - a.value));
            setTotal(fallbackItems.reduce((acc, it) => acc + it.value, 0));
          }
        }
      } catch (_e) {
        if (!mounted) return;
        setSeries(fallbackSeries);
        const sorted = fallbackItems.slice().sort((a, b) => b.value - a.value);
        setItems(sorted);
        setTotal(sorted.reduce((acc, it) => acc + it.value, 0));
      }
    }

    load();
    return () => {
      mounted = false;
    };
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

  return (
    <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
      <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.kicker}>Collection Value</Text>
            <Text style={styles.total}>{formatMoneyEUR(total)}</Text>
          </View>

          <Pressable
            accessibilityRole="button"
            style={styles.settingsBtn}
            onPress={() => {
              // Keep this non-destructive; wire later.
              // You can route to settings if you already have it.
            }}
          >
            <Ionicons name="settings-outline" size={20} color={stylesVars.navy} />
          </Pressable>
        </View>

        {/* Range toggles */}
        <View style={styles.rangeRow}>
          {rangeButtons.map((k) => {
            const active = k === range;
            return (
              <Pressable
                key={k}
                accessibilityRole="button"
                onPress={() => setRange(k)}
                style={[styles.rangeBtn, active ? styles.rangeBtnActive : null]}
              >
                <Text style={[styles.rangeText, active ? styles.rangeTextActive : null]}>{k}</Text>
              </Pressable>
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
};

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: stylesVars.bg },
  container: { paddingHorizontal: 16, paddingTop: 10, paddingBottom: 22 },

  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 10,
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
  pctUp: { color: "#0A7D4E" },
  pctDown: { color: "#B42318" },
});
TSX

echo "OK: Patched $TARGET"
echo "Backup: ${TARGET}.bak_${TS}"
