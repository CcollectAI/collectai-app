import React, { useMemo, useState } from "react";
import { View, Text, ActivityIndicator, TouchableOpacity } from "react-native";
import Svg, { Path, Defs, LinearGradient, Stop, Rect } from "react-native-svg";
import { theme } from "../theme";
import usePortfolioSeries from "../hooks/usePortfolioSeries";

const CURRENCY = new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export default function PortfolioChart() {
  const { data, loading } = usePortfolioSeries();
  const [range, setRange] = useState<"7d" | "30d" | "90d">("30d");

  const filtered = useMemo(() => {
    const n = range === "7d" ? 7 : range === "90d" ? 90 : 30;
    return data.slice(-n);
  }, [data, range]);

  const { total, deltaPct, path, fillPath } = useMemo(() => {
    const pts = filtered.length ? filtered : data;
    const total = pts.length ? pts[pts.length - 1].v : 0;
    const deltaPct = pts.length >= 2 ? ((pts[pts.length - 1].v - pts[0].v) / pts[0].v) * 100 : 0;

    const w = 320, h = 120;
    if (!pts.length) return { total, deltaPct, path: "", fillPath: "" };

    const ys = pts.map(p => p.v);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const spanY = Math.max(1, maxY - minY);
    const px = (i: number) => (i / Math.max(1, pts.length - 1)) * (w - 2) + 1;
    const py = (v: number) => h - ((v - minY) / spanY) * (h - 2) - 1;

    let d = `M ${px(0)},${py(ys[0])}`;
    for (let i = 1; i < pts.length; i++) d += ` L ${px(i)},${py(ys[i])}`;
    const dFill = `${d} L ${px(pts.length - 1)},${h} L ${px(0)},${h} Z`;

    return { total, deltaPct, path: d, fillPath: dFill };
  }, [filtered, data]);

  const positive = deltaPct >= 0;

  return (
    <View
      style={{
        backgroundColor: "#fff",
        borderRadius: theme.radius["2xl"],
        marginHorizontal: theme.spacing.lg,
        marginBottom: theme.spacing.lg,
        padding: theme.spacing.lg,
        borderWidth: 1,
        borderColor: theme.colors.border,
        ...theme.shadow.card,
      }}
    >
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <Text style={{ fontSize: 16, fontWeight: "700", color: theme.colors.muted }}>Your Portfolio</Text>
        <View style={{ flexDirection: "row", gap: 8 }}>
          {(["7d","30d","90d"] as const).map((r) => {
            const active = range === r;
            return (
              <TouchableOpacity
                key={r}
                onPress={() => setRange(r)}
                style={{
                  backgroundColor: active ? theme.colors.brand.light : "#fff",
                  borderWidth: 1,
                  borderColor: theme.colors.border,
                  borderRadius: 999,
                  paddingHorizontal: 10,
                  paddingVertical: 6,
                  marginLeft: 8,
                }}
              >
                <Text style={{ fontWeight: "800", color: active ? "#0F172A" : theme.colors.muted }}>{r.toUpperCase()}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      <View style={{ height: 8 }} />

      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <Text style={{ fontSize: 28, fontWeight: "900", color: theme.colors.text }}>{CURRENCY.format(total || 0)}</Text>
        <View style={{ backgroundColor: positive ? "#ECFDF5" : "#FEF2F2", paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999 }}>
          <Text style={{ fontWeight: "800", color: positive ? theme.colors.success : theme.colors.danger }}>
            {`${positive ? "▲" : "▼"} ${Math.abs(deltaPct).toFixed(1)}%`}
          </Text>
        </View>
      </View>

      <View style={{ height: 8 }} />

      <View style={{ width: "100%", height: 140, alignItems: "center", justifyContent: "center" }}>
        {loading && !data.length ? (
          <ActivityIndicator />
        ) : (
          <Svg width="100%" height="140" viewBox="0 0 320 140">
            <Defs>
              <LinearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                <Stop offset="0" stopColor="#81D8D0" stopOpacity="0.38" />
                <Stop offset="1" stopColor="#81D8D0" stopOpacity="0.02" />
              </LinearGradient>
            </Defs>
            <Rect x="0" y="0" width="320" height="140" fill="transparent" />
            <Path d={fillPath} fill="url(#g)" />
            <Path d={path} stroke="#44A9A1" strokeWidth={2.5} fill="none" />
          </Svg>
        )}
      </View>
    </View>
  );
}
