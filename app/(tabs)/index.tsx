import React, { useEffect, useMemo, useRef, useState } from "react";
import { View, Text, ScrollView, Pressable, StyleSheet, Platform } from "react-native";
import { PanResponder } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Polyline, Line, Circle, Text as SvgText } from "react-native-svg";
import { Ionicons } from "@expo/vector-icons";
import { useWatchlist } from "@/state/watchlistStore";
import { useRouter, Link } from "expo-router";

import { usePortfolioWatchlist } from "src/ui/usePortfolioWatchlist";
import { typography } from "@/ui/typography";
// Theme: use app theme when available; fallback is safe.
let themeApi: any = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  themeApi = require("@/theme");
} catch (_e) {
  themeApi = null;
}

function getThemeVars() {
  const t = themeApi?.theme ?? themeApi?.default?.theme;
  const c = t?.colors ?? {};
  return {
    bg: c.background ?? "#FFFFFF",
    card: c.card ?? "#FFFFFF",
    border: c.border ?? "rgba(11,27,58,0.10)",
    text: c.text ?? "#0B1B3A",
    muted: c.subtext ?? c.mutedText ?? "rgba(11,27,58,0.65)",
    navy: c.navy ?? "#0B1B3A",
    tiffany: c.tiffany ?? "#38D6C7",
    grid: c.grid ?? "rgba(11,27,58,0.10)",
    success: c.success ?? "#0A7D4E",
    danger: c.danger ?? "#B42318",
  };
}


// Watchlist: keep it crash-proof (repo has a couple implementations)
let watchlistApi: any = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  watchlistApi = require("@/src/state/watchlistStore");
} catch (_e) {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    watchlistApi = require("../src/state/watchlistStore");
  } catch (_e2) {
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      watchlistApi = require("@/state/watchlistStore");
    } catch (_e3) {
      watchlistApi = null;
    }
  }
}

type RangeKey = "1D" | "7D" | "30D";


// --- Canonical navigation targets (single source of truth) ---
// Item card route exists: app/item/[id].tsx  => /item/:id
const ITEM_CARD_ROUTE = (id: string) => `/item/${encodeURIComponent(id)}`;

// Event card route: prefer your existing event card route.
// If your card is different, change ONLY this one line.
// If you have app/events/[eventId].tsx => /events/:eventId
const EVENT_CARD_ROUTE = (id: string) => `/events/${encodeURIComponent(id)}`;
type PortfolioPoint = { t: number; v: number };
type ItemRow = { id: string; name: string; category?: string; value: number; changePct?: number };
type WatchRow = { id: string; name: string; value: number; changePct?: number };

function formatMoneyEUR(n: number) {
  try {
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(n);
  } catch {
    return `€${Math.round(n).toLocaleString("en-GB")}`;
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
  return { min, max, pts: points.map((p) => ({ ...p, nv: (p.v - min) / span })) };
}

// Optional portfolio analytics store (safe fallback)
let analyticsApi: any = null;
try {
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

function extractSeries(raw: any): PortfolioPoint[] {
  const arr = (Array.isArray(raw) && raw) || raw?.points || raw?.series || raw?.data || [];
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
  const base = raw?.items || raw?.holdings || raw?.positions || raw?.snapshot?.items || raw?.snapshot?.holdings || [];
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

      const collectionName = String(
        it?.collectionName ?? it?.collection ?? it?.setName ?? it?.set ?? it?.series ?? ""
      ) || undefined;
      const year = Number.isFinite(Number(it?.year)) ? Number(it.year) : undefined;

      if (!Number.isFinite(value)) return null;
      return { id, name, category, collectionName, year, value, changePct };
    })
    .filter(Boolean) as ItemRow[];
}

export default function PortfolioScreen() {
  const router = useRouter();
  const vars = useMemo(() => getThemeVars(), []);
  const styles = useMemo(() => makeStyles(vars), [vars]);

  const [range, setRange] = useState<RangeKey>("7D");
const [chartW, setChartW] = useState<number>(0);

  const [series, setSeries] = useState<PortfolioPoint[]>([]);
  const [items, setItems] = useState<ItemRow[]>([]);
    const [watch, setWatch] = useState<any[]>([]);
  const [total, setTotal] = useState<number>(0);

  // Watchlist (fallback-safe)
  const watchHook = watchlistApi?.useWatchlist;
  const watchSnap = watchHook ? watchHook() : null;
  const watchItemsObj = (watchSnap && (watchSnap.items || watchSnap.watch || watchSnap.watchlist)) || {};
  const watchList = Array.isArray(watchItemsObj)
    ? watchItemsObj
    : Object.values(watchItemsObj || {});
  const [alerts, setAlerts] = useState<Record<string, boolean>>({});

  // Robinhood-like chart scrub
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const wl = useWatchlist();
  const watchItems = Object.values((wl as any)?.items ?? {});
  const watchAlerts = (wl as any)?.alerts ?? {};
  useEffect(() => {
    let mounted = true;

    async function load() {
      const fallbackSeries: PortfolioPoint[] = [
        { t: 0, v: 12400 }, { t: 1, v: 12340 }, { t: 2, v: 12510 }, { t: 3, v: 12680 },
        { t: 4, v: 12590 }, { t: 5, v: 12840 }, { t: 6, v: 13120 }, { t: 7, v: 13040 },
        { t: 8, v: 13310 }, { t: 9, v: 13480 }, { t: 10, v: 13290 }, { t: 11, v: 13610 },
      ];

      const fallbackItems: ItemRow[] = [
        { id: "1", name: "PSA 10 Lugia (Neo Genesis)", category: "Pokémon", value: 3450, changePct: 0.028 },
        { id: "2", name: "Gunpla MG Barbatos (built)", category: "Gunpla", value: 1820, changePct: -0.011 },
        { id: "3", name: "Funko: Vaulted Grail", category: "Funko", value: 1250, changePct: 0.007 },
        { id: "4", name: "Warhammer Army Lot", category: "Warhammer", value: 980, changePct: 0.014 },
        { id: "5", name: "Designer Toy (limited run)", category: "Art Toys", value: 760, changePct: -0.006 },
      ];

      const fallbackEvents = [
        { id: 'e1', title: 'Drop: Neo Genesis Restock', date: 'Dec 21, 2025', location: 'Online', tag: 'Drop', severity: 'High' },
        { id: 'e2', title: 'Local Card Show (Utrecht)', date: 'Dec 28, 2025', location: 'Utrecht', tag: 'Event', severity: 'Medium' },
        { id: 'e3', title: 'Twitch Live: Market Recap', date: 'Jan 4, 2026', location: 'Twitch', tag: 'Stream', severity: 'Low' },
      ];


      const fallbackWatch: WatchRow[] = [
        { id: "w1", name: "Sealed Booster Box (watch)", value: 520, changePct: 0.012 },
        { id: "w2", name: "Lorcana Enchanted (watch)", value: 410, changePct: -0.008 },
        { id: "w3", name: "LEGO retired set (watch)", value: 690, changePct: 0.004 },
      ];

      try {
        // series
        if (analyticsApi?.fetchPortfolioSeries) {
          const raw = await analyticsApi.fetchPortfolioSeries({ range });
          const s = extractSeries(raw);
          if (mounted) setSeries(s.length ? s : fallbackSeries);
        } else {
          if (mounted) setSeries(fallbackSeries);
        }

        // items
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
            const sorted = fallbackItems.slice().sort((a, b) => b.value - a.value);
            setItems(sorted);
            setTotal(sorted.reduce((acc, it) => acc + it.value, 0));
          }
        }

        if (mounted) {
          setWatch(fallbackWatch);
          setAlerts((prev) => prev); // keep any toggles
        }
      } catch (_e) {
        if (!mounted) return;
        setSeries(fallbackSeries);
        const sorted = fallbackItems.slice().sort((a, b) => b.value - a.value);
        setItems(sorted);
        setTotal(sorted.reduce((acc, it) => acc + it.value, 0));
        setWatch(fallbackWatch);
      }
    }

    load();
    return () => {
      mounted = false;
    };
  }, [range]);

  const norm = useMemo(() => normalizeSeries(series), [series]);
  const chart = norm.pts;

  // Chart geometry (SVG covers the WHOLE card including the button area)
  const W = 320;
  const H = 215;
  const TOP_UI = 44; // space where the range buttons sit, still inside the card/graph area
  const PAD_X = 46; // left gutter for Y labels  // left space for y labels
  const PAD_Y = 16;
  const PLOT_TOP = TOP_UI + PAD_Y;
  const PLOT_BOTTOM = H - PAD_Y;

  
  // --- Robinhood-style drag hover ---
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

  const panResponder = useMemo(() => {
    return PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (evt) => {
        const x = evt.nativeEvent.locationX ?? 0;
        const n = Array.isArray(chart) ? chart.length : 0;
        if (!n || !chartW) return;
        const i = clamp(Math.round((x / chartW) * (n - 1)), 0, n - 1);
        setHoverIndex(i);
      },
      onPanResponderMove: (evt) => {
        const x = evt.nativeEvent.locationX ?? 0;
        const n = Array.isArray(chart) ? chart.length : 0;
        if (!n || !chartW) return;
        const i = clamp(Math.round((x / chartW) * (n - 1)), 0, n - 1);
        setHoverIndex(i);
      },
      onPanResponderRelease: () => {},
      onPanResponderTerminate: () => {},
    });
  }, [chart, chartW]);
  
const polylinePoints = useMemo(() => {
    if (!Array.isArray(chart) || chart.length === 0) return "";
    const n = chart.length;
    return chart
      .map((p: any, i: number) => {
        const x = PAD_X + (i * (W - PAD_X - 12)) / Math.max(1, n - 1);
        const y = PLOT_TOP + (1 - clamp01(p.nv)) * (PLOT_BOTTOM - PLOT_TOP);
        return `${x},${y}`;
      })
      .join(" ");
  }, [chart]);

  const scrubToX = (x: number) => {
    if (!chart.length || !chartW) return;
    const n = chart.length;
    const clamped = Math.max(0, Math.min(chartW, x));
    const t = clamped / Math.max(1, chartW);
    const i = Math.round(t * (n - 1));
    setHoverIndex(Math.max(0, Math.min(n - 1, i)));
  };

  const pan = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderGrant: (evt) => {
          scrubToX(evt.nativeEvent.locationX);
        },
        onPanResponderMove: (evt) => {
          scrubToX(evt.nativeEvent.locationX);
        },
        onPanResponderRelease: () => {
          setHoverIndex(null);
        },
        onPanResponderTerminate: () => {
          setHoverIndex(null);
        },
      }),
    [chartW, chart]
  );

  const hovered = hoverIndex !== null && chart[hoverIndex] ? chart[hoverIndex] : null;


  const minV = norm.min ?? 0;
  const maxV = norm.max ?? 0;
  const midV = (minV + maxV) / 2;

  const rangeButtons: RangeKey[] = ["1D", "7D", "30D"];

  const topEvents = [
    { id: "e1", title: "Drop: Holiday restock", meta: "Today • 18:00" },
    { id: "e2", title: "Creator live stream", meta: "Sat • 20:00" },
    { id: "e3", title: "New category wave", meta: "Next week" },
  ];

  return (
    <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
      <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.kicker}>Collection Value</Text>
            <Text style={styles.total}>{formatMoneyEUR(hovered?.v ?? total)}</Text>
          </View>

          {/* Twitch icon remains (your existing wiring should route it) */}
          <Pressable
            accessibilityRole="button"
            style={styles.iconBtn}
            onPress={() => router.push("/twitch")}
          >
            <Ionicons name="logo-twitch" size={18} color={vars.text} />
          </Pressable>
        </View>

        {/* Chart card */}
        <View style={styles.card}>
          {/* Range toggles integrated into the chart area */}
          <View style={styles.rangeOverlay}>
            {rangeButtons.map((k) => {
              const active = k === range;
              return (
                <Pressable
                  key={k}
                  accessibilityRole="button"
                  onPress={() => setRange(k)}
                  style={[styles.rangePill, active ? styles.rangePillActive : null]}
                >
                  <Text style={[styles.rangePillText, active ? styles.rangePillTextActive : null]}>{k}</Text>
                </Pressable>
              );
            })}
          </View>

          <View

            onLayout={(e) => setChartW(e.nativeEvent.layout.width)}

            {...pan.panHandlers}

          >

          <Svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
            {/* gridlines — extend through the TOP_UI area too */}
            <Line x1={0} y1={PLOT_TOP} x2={W} y2={PLOT_TOP} stroke={vars.grid} strokeWidth={1} />
            <Line x1={0} y1={(PLOT_TOP + PLOT_BOTTOM) / 2} x2={W} y2={(PLOT_TOP + PLOT_BOTTOM) / 2} stroke={vars.grid} strokeWidth={1} />
            <Line x1={0} y1={PLOT_BOTTOM} x2={W} y2={PLOT_BOTTOM} stroke={vars.grid} strokeWidth={1} />

            {/* y labels (EUR totals) */}
            <SvgText x={8} y={PLOT_TOP + 4} fontSize="10" fill={vars.muted}>{formatMoneyEUR(maxV)}</SvgText>
            <SvgText x={8} y={(PLOT_TOP + PLOT_BOTTOM) / 2 + 4} fontSize="10" fill={vars.muted}>{formatMoneyEUR(midV)}</SvgText>
            <SvgText x={8} y={PLOT_BOTTOM + 2} fontSize="10" fill={vars.muted}>{formatMoneyEUR(minV)}</SvgText>

            {/* series */}
            <Polyline
              points={polylinePoints}
              fill="none"
              stroke={vars.tiffany}
              strokeWidth={3}
              strokeLinejoin="round"
              strokeLinecap="round"
            />

              {hovered ? (
                <>
                  <Line
                    x1={PAD_X + (hoverIndex! * (W - PAD_X - 12)) / Math.max(1, chart.length - 1)}
                    y1={PLOT_TOP}
                    x2={PAD_X + (hoverIndex! * (W - PAD_X - 12)) / Math.max(1, chart.length - 1)}
                    y2={PLOT_BOTTOM}
                    stroke={vars.muted}
                    strokeWidth={1}
                    strokeDasharray="4 4"
                  />
                  <Circle
                    cx={PAD_X + (hoverIndex! * (W - PAD_X - 12)) / Math.max(1, chart.length - 1)}
                    cy={PLOT_TOP + (1 - clamp01(hovered.nv)) * (PLOT_BOTTOM - PLOT_TOP)}
                    r={5}
                    fill={vars.tiffany}
                  />
                </>
              ) : null}

          </Svg>
            </View>
            </View>

            {/* Collection section */}
        <View style={styles.sectionRow}>
          <Text style={styles.sectionTitle}>Collection</Text>
          <Text style={styles.sectionRight}>{items.length ? `${items.length} items` : ""}</Text>
        </View>

        <View style={styles.listCard}>
          {items.slice(0, 10).map((it, idx) => {
            const isUp = (it.changePct ?? 0) >= 0;
            return (
              <Pressable
                key={it.id}
                style={[styles.row, idx === 0 ? styles.rowFirst : null]}
                onPress={() => router.push(`/item/${encodeURIComponent(it.id)}`)}
              >
                <View style={styles.rowLeft}>
                  <Text style={styles.rowName} numberOfLines={1}>{it.name}</Text>
                  <Text style={styles.rowMeta} numberOfLines={1}>
                    <Text style={styles.metaLabel}>Collection</Text>
                    <Text style={styles.metaDot}> • </Text>
                    <Text style={styles.metaValue}>{it.category ? it.category : "—"}</Text>
                    <Text style={styles.metaDot}> • </Text>
                    <Text style={[styles.metaValue, isUp ? styles.pctUp : styles.pctDown]}>{formatPct(it.changePct)}</Text>
                  </Text>
                </View>

                <View style={styles.rowRight}>
                  <Text style={styles.rowValue}>{formatMoneyEUR(it.value)}</Text>
                </View>
              </Pressable>
            );
          })}
        </View>

        {/* Clear analytics ingress */}
        <Link href="/analytics" asChild>
          <Pressable style={styles.ctaRow}>
            <View style={styles.ctaLeft}>
              <Ionicons name="analytics-outline" size={18} color={vars.text} />
              <Text style={styles.ctaText}>Collection analytics</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={vars.muted} />
          </Pressable>
        </Link>

        {/* Watchlist + price alerts */}
        <View style={styles.sectionRow}>
          <Text style={styles.sectionTitle}>Watchlist</Text>
          <Text style={styles.sectionRight}>{(watch?.length ?? 0) ? `${(watch?.length ?? 0)}` : ""}</Text>
        </View>

        <View style={styles.listCard}>
          {watch.slice(0, 6).map((w, idx) => {
            const isUp = (w.changePct ?? 0) >= 0;
            const alertOn = !!alerts[w.id];
            return (
              <View key={w.id} style={[styles.row, idx === 0 ? styles.rowFirst : null]}>
                <View style={styles.rowLeft}>
                  <Text style={styles.rowName} numberOfLines={1}>{w.name}</Text>
                  <Text style={styles.rowMeta} numberOfLines={1}>
                    <Text style={[styles.metaValue, isUp ? styles.pctUp : styles.pctDown]}>{formatPct(w.changePct)}</Text>
                  </Text>
                </View>

                <View style={styles.watchRight}>
                  <Text style={styles.rowValue}>{formatMoneyEUR(w.value)}</Text>
                  <Pressable
                    accessibilityRole="button"
                    onPress={() => setAlerts((prev) => ({ ...prev, [w.id]: !prev[w.id] }))}
                    style={styles.bellBtn}
                  >
                    <Ionicons
                      name={alertOn ? "notifications" : "notifications-outline"}
                      size={18}
                      color={alertOn ? vars.tiffany : vars.muted}
                    />
                  </Pressable>
                </View>
                </View>
            );
          })}
        </View>

        {/* Upcoming events/drops BELOW watchlist */}
        <View style={styles.sectionRow}>
          <Text style={styles.sectionTitle}>Upcoming events & drops</Text>
          <Text style={styles.sectionRight}>Top 3</Text>
        </View>

        <View style={styles.listCard}>
          {topEvents.map((e, idx) => (
            <Pressable
              key={e.id}
              style={[styles.row, idx === 0 ? styles.rowFirst : null]}
              onPress={() => router.push(`/event-card?id=${encodeURIComponent(e.id)}`)}
            >
              <View style={styles.rowLeft}>
                <Text style={styles.rowName} numberOfLines={1}>{e.title}</Text>
                <Text style={styles.rowMeta} numberOfLines={1}>
                  <Text style={styles.metaValue}>{e.meta}</Text>
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={vars.muted} />
            </Pressable>
          ))}
        </View>

        <View style={{ height: Platform.OS === "ios" ? 24 : 18 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function makeStyles(v: ReturnType<typeof getThemeVars>) {
  return StyleSheet.create({
    safe: { flex: 1, backgroundColor: "#FFFFFF" },
    container: { paddingHorizontal: 16, paddingTop: 10, paddingBottom: 22 },

    headerRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 10,
    },
    kicker: { color: v.muted, fontSize: 13, marginBottom: 4, fontWeight: "600" },
    total: { color: v.text, fontSize: 30, fontWeight: "700" },

    iconBtn: {
      width: 36,
      height: 36,
      backgroundColor: "#FFFFFF",
      borderWidth: 1,
      borderColor: v.border,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 0,
    },

    card: {
      backgroundColor: "#FFFFFF",
      borderWidth: 1,
      borderColor: v.border,
      padding: 12,
      marginBottom: 14,
      borderRadius: 0,
      overflow: "hidden",
    },

    // range buttons inside chart area (overlay)
    rangeOverlay: {
      position: "absolute",
      top: 10,
      right: 10,
      zIndex: 10,
      flexDirection: "row",
      gap: 8,
    },
    rangePill: {
      paddingVertical: 6,
      paddingHorizontal: 10,
      backgroundColor: "rgba(255,255,255,0.90)",
      borderWidth: 1,
      borderColor: v.border,
      borderRadius: 999,
    },
    rangePillActive: {
      backgroundColor: "rgba(56,214,199,0.16)",
      borderColor: "rgba(56,214,199,0.35)",
    },
    rangePillText: { color: v.muted, fontWeight: "600", fontSize: 12 },
    rangePillTextActive: { color: v.text },

    sectionRow: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "baseline",
      marginTop: 6,
      marginBottom: 10,
    },
    sectionTitle: { ...typography.h3 },
    sectionRight: { fontSize: 12, fontWeight: "600", color: v.muted },

    listCard: {
      backgroundColor: "#FFFFFF",
      borderWidth: 1,
      borderColor: v.border,
      borderRadius: 0,
      marginBottom: 12,
    },
    row: {
      flexDirection: "row",
      justifyContent: "space-between",
      paddingVertical: 12,
      paddingHorizontal: 12,
      borderTopWidth: 1,
      borderTopColor: v.border,
      alignItems: "center",
    },
    rowFirst: { borderTopWidth: 0 },
    rowLeft: { flex: 1, paddingRight: 10 },

    rowName: { color: v.text, fontWeight: "700", fontSize: 14 },
    rowMeta: { marginTop: 4, fontSize: 12, fontWeight: "600", color: v.muted },
    metaLabel: { color: "rgba(11,27,58,0.45)", fontWeight: "600" },
    metaValue: { color: v.muted, fontWeight: "600" },
    metaDot: { color: "rgba(11,27,58,0.25)", fontWeight: "600" },

    rowRight: { alignItems: "flex-end", minWidth: 92 },
    rowValue: { color: v.text, fontWeight: "600", fontSize: 14 },

    watchRight: { flexDirection: "row", alignItems: "center", gap: 10 },
    bellBtn: {
      width: 32,
      height: 32,
      borderWidth: 1,
      borderColor: v.border,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: "#FFFFFF",
      borderRadius: 999,
    },

    pctUp: { color: v.success },
    pctDown: { color: v.danger },

    ctaRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingVertical: 12,
      paddingHorizontal: 12,
      borderWidth: 1,
      borderColor: v.border,
      backgroundColor: "#FFFFFF",
      borderRadius: 0,
      marginBottom: 6,
    },
    ctaLeft: { flexDirection: "row", alignItems: "center", gap: 10 },
    ctaText: { color: v.text, fontWeight: "600", fontSize: 14 },
  });
}