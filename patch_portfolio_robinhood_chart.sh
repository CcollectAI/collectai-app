#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

PORTFOLIO_FILE="app/(tabs)/index.tsx"
BACKUP_FILE="${PORTFOLIO_FILE}.bak_portfolio_robinhood_$(date +%Y%m%d-%H%M%S)"

if [ -f "$PORTFOLIO_FILE" ]; then
  cp "$PORTFOLIO_FILE" "$BACKUP_FILE"
  echo "📦 Backed up existing portfolio screen to:"
  echo "  $BACKUP_FILE"
else
  echo "⚠️  $PORTFOLIO_FILE not found, creating new portfolio screen."
fi

cat > "$PORTFOLIO_FILE" <<'TSX'
import React, { useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  ScrollView,
  TouchableOpacity,
  Pressable,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

/**
 * Robinhood-style portfolio screen prototype.
 *
 * - Uses built-in React Native components only (no extra chart libraries).
 * - Chart is made of interactive segments; tap to "hover" a point.
 * - Fully padded so nothing bleeds off the edges of the screen.
 * - Time range buttons (1D / 7D / 30D) stay inside safe horizontal padding.
 */

type RangeKey = "1D" | "7D" | "30D";

type Point = {
  t: string;   // label (e.g., "10:15", "Mon", "Nov")
  v: number;   // value
};

const RANGE_POINTS: Record<RangeKey, Point[]> = {
  "1D": [
    { t: "09:30", v: 1220 },
    { t: "10:15", v: 1240 },
    { t: "11:00", v: 1230 },
    { t: "12:30", v: 1255 },
    { t: "14:00", v: 1275 },
    { t: "15:30", v: 1265 },
    { t: "16:00", v: 1282 },
  ],
  "7D": [
    { t: "Mon", v: 1180 },
    { t: "Tue", v: 1195 },
    { t: "Wed", v: 1210 },
    { t: "Thu", v: 1205 },
    { t: "Fri", v: 1235 },
    { t: "Sat", v: 1248 },
    { t: "Sun", v: 1262 },
  ],
  "30D": [
    { t: "W1", v: 1100 },
    { t: "W2", v: 1145 },
    { t: "W3", v: 1170 },
    { t: "W4", v: 1190 },
    { t: "W5", v: 1225 },
    { t: "W6", v: 1210 },
    { t: "W7", v: 1240 },
    { t: "W8", v: 1275 },
  ],
};

const formatCurrency = (value: number): string => {
  return value.toLocaleString(undefined, {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const getChange = (points: Point[]) => {
  if (!points.length) return { abs: 0, pct: 0 };
  const first = points[0].v;
  const last = points[points.length - 1].v;
  const abs = last - first;
  const pct = first === 0 ? 0 : (abs / first) * 100;
  return { abs, pct };
};

const PortfolioScreen: React.FC = () => {
  const [range, setRange] = useState<RangeKey>("1D");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const points = useMemo(() => RANGE_POINTS[range], [range]);

  const { abs, pct } = useMemo(() => getChange(points), [points]);
  const latestValue = points.length ? points[points.length - 1].v : 0;

  const selectedIndex =
    hoverIndex !== null && hoverIndex >= 0 && hoverIndex < points.length
      ? hoverIndex
      : points.length - 1;

  const selectedPoint = points[selectedIndex] ?? null;

  const isGain = abs >= 0;
  const changeColor = isGain ? "#16A34A" : "#DC2626";

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Header: title + settings placeholder */}
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.title}>Portfolio</Text>
            <Text style={styles.subtitle}>Total collection value</Text>
          </View>
          <View style={styles.settingsIconCircle}>
            <Ionicons name="settings-outline" size={18} color="#1F2933" />
          </View>
        </View>

        {/* Total value + change */}
        <View style={styles.totalRow}>
          <Text style={styles.totalValue}>{formatCurrency(latestValue)}</Text>
          <View style={styles.changeRow}>
            <Ionicons
              name={isGain ? "caret-up" : "caret-down"}
              size={14}
              color={changeColor}
            />
            <Text style={[styles.changeText, { color: changeColor }]}>
              {abs >= 0 ? "+" : ""}
              {formatCurrency(abs)} ({abs >= 0 ? "+" : ""}
              {pct.toFixed(2)}%)
            </Text>
          </View>
          {selectedPoint && (
            <Text style={styles.selectedPointLabel}>
              {selectedPoint.t} · {formatCurrency(selectedPoint.v)}
            </Text>
          )}
        </View>

        {/* Range selectors */}
        <View style={styles.rangeRow}>
          {(["1D", "7D", "30D"] as RangeKey[]).map((key) => {
            const active = key === range;
            return (
              <TouchableOpacity
                key={key}
                style={[
                  styles.rangeButton,
                  active && styles.rangeButtonActive,
                ]}
                onPress={() => {
                  setRange(key);
                  setHoverIndex(null);
                }}
              >
                <Text
                  style={[
                    styles.rangeButtonText,
                    active && styles.rangeButtonTextActive,
                  ]}
                >
                  {key}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Chart area */}
        <View style={styles.chartCard}>
          <View style={styles.chartInner}>
            {/* Y-axis min/max labels (optional, simple) */}
            <View style={styles.yAxis}>
              <Text style={styles.yAxisLabel}>
                {points.length ? formatCurrency(Math.max(...points.map((p) => p.v))) : ""}
              </Text>
              <Text style={styles.yAxisLabel}>
                {points.length ? formatCurrency(Math.min(...points.map((p) => p.v))) : ""}
              </Text>
            </View>

            {/* Interactive segments */}
            <View style={styles.chartSegmentsContainer}>
              {points.map((p, idx) => {
                if (!points.length) return null;

                // Normalize height
                const values = points.map((pt) => pt.v);
                const min = Math.min(...values);
                const max = Math.max(...values);
                const norm =
                  max === min ? 0.5 : (p.v - min) / (max - min); // 0..1
                const barHeight = 40 + norm * 80; // 40..120

                const isSelected = idx === selectedIndex;

                return (
                  <Pressable
                    key={idx}
                    style={styles.chartSegmentPressable}
                    onPress={() => setHoverIndex(idx)}
                  >
                    <View style={styles.chartSegmentColumn}>
                      {/* Vertical bar */}
                      <View
                        style={[
                          styles.chartBar,
                          {
                            height: barHeight,
                            opacity: isSelected ? 1 : 0.4,
                          },
                        ]}
                      />
                      {/* Circle at the top */}
                      <View
                        style={[
                          styles.chartDot,
                          isSelected && styles.chartDotSelected,
                        ]}
                      />
                    </View>
                    <Text style={styles.chartTickLabel}>{p.t}</Text>
                  </Pressable>
                );
              })}
            </View>
          </View>
        </View>

        {/* Placeholder: collection list below chart */}
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionTitle}>Collection</Text>
          <Text style={styles.sectionSubtitle}>Top positions by value</Text>
        </View>

        <View style={styles.collectionCard}>
          <View style={styles.collectionRow}>
            <View>
              <Text style={styles.collectionName}>Pokémon · Modern slabs</Text>
              <Text style={styles.collectionSub}>
                12 items · {formatCurrency(742)}
              </Text>
            </View>
            <Text style={styles.collectionValue}>{formatCurrency(742)}</Text>
          </View>
          <View style={styles.collectionRow}>
            <View>
              <Text style={styles.collectionName}>Gunpla & kits</Text>
              <Text style={styles.collectionSub}>
                8 items · {formatCurrency(514)}
              </Text>
            </View>
            <Text style={styles.collectionValue}>{formatCurrency(514)}</Text>
          </View>
          <View style={styles.collectionRow}>
            <View>
              <Text style={styles.collectionName}>Designer toys</Text>
              <Text style={styles.collectionSub}>
                5 items · {formatCurrency(278)}
              </Text>
            </View>
            <Text style={styles.collectionValue}>{formatCurrency(278)}</Text>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#F5F7FA",
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 32,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  title: {
    fontSize: 20,
    fontWeight: "700",
  },
  subtitle: {
    fontSize: 12,
    opacity: 0.7,
  },
  settingsIconCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#E5F4F8",
  },
  totalRow: {
    marginBottom: 8,
  },
  totalValue: {
    fontSize: 28,
    fontWeight: "700",
  },
  changeRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 4,
  },
  changeText: {
    fontSize: 13,
    marginLeft: 4,
  },
  selectedPointLabel: {
    marginTop: 4,
    fontSize: 12,
    opacity: 0.7,
  },
  rangeRow: {
    flexDirection: "row",
    justifyContent: "flex-start",
    gap: 8,
    marginTop: 12,
    marginBottom: 8,
  },
  rangeButton: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "#CBD5E1",
    backgroundColor: "#FFFFFF",
  },
  rangeButtonActive: {
    borderColor: "#14B8A6",
    backgroundColor: "#CCFBF1",
  },
  rangeButtonText: {
    fontSize: 12,
    opacity: 0.8,
  },
  rangeButtonTextActive: {
    opacity: 1,
    fontWeight: "600",
  },
  chartCard: {
    marginTop: 4,
    marginBottom: 16,
    padding: 12,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    elevation: 1,
    shadowColor: "#000",
    shadowOpacity: 0.04,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 3 },
  },
  chartInner: {
    flexDirection: "row",
  },
  yAxis: {
    justifyContent: "space-between",
    marginRight: 8,
  },
  yAxisLabel: {
    fontSize: 10,
    opacity: 0.6,
  },
  chartSegmentsContainer: {
    flex: 1,
    flexDirection: "row",
    alignItems: "flex-end",
    height: 160,
    overflow: "hidden",
  },
  chartSegmentPressable: {
    flex: 1,
    alignItems: "center",
    justifyContent: "flex-end",
  },
  chartSegmentColumn: {
    alignItems: "center",
    justifyContent: "flex-end",
    marginBottom: 4,
  },
  chartBar: {
    width: 6,
    borderRadius: 999,
    backgroundColor: "#14B8A6",
  },
  chartDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#E0F2F1",
    marginTop: 4,
  },
  chartDotSelected: {
    backgroundColor: "#14B8A6",
  },
  chartTickLabel: {
    fontSize: 9,
    opacity: 0.65,
  },
  sectionHeaderRow: {
    marginTop: 4,
    marginBottom: 4,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "600",
  },
  sectionSubtitle: {
    fontSize: 12,
    opacity: 0.7,
  },
  collectionCard: {
    borderRadius: 12,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  collectionRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    paddingVertical: 6,
  },
  collectionName: {
    fontSize: 13,
    fontWeight: "500",
  },
  collectionSub: {
    fontSize: 11,
    opacity: 0.7,
  },
  collectionValue: {
    fontSize: 13,
    fontWeight: "600",
  },
});

export default PortfolioScreen;
TSX

echo "✅ Replaced $PORTFOLIO_FILE with a Robinhood-style portfolio prototype (backed up original)."
