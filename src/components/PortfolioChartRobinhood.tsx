import React, { useMemo, useState } from "react";
import { View, Text, StyleSheet, Pressable } from "react-native";
import { formatPrice } from "@/lib/format";

export type PortfolioPoint = {
  label: string;   // "09:30", "Mon", etc.
  value: number;   // numeric portfolio value
};

type Props = {
  data: PortfolioPoint[];
};

/**
 * Robinhood-style mini chart:
 * - No external libraries
 * - Fully padded: no edge bleed
 * - Tap columns to "hover" a point
 * - Intended to sit inside a card on the Portfolio screen
 */
export default function PortfolioChartRobinhood({ data }: Props) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const effectiveData = data && data.length > 0 ? data : [];

  const { min, max } = useMemo(() => {
    if (!effectiveData.length) return { min: 0, max: 0 };
    const values = effectiveData.map((p) => p.value);
    return {
      min: Math.min(...values),
      max: Math.max(...values),
    };
  }, [effectiveData]);

  const selectedIndex =
    hoverIndex !== null &&
    hoverIndex >= 0 &&
    hoverIndex < effectiveData.length
      ? hoverIndex
      : effectiveData.length - 1;

  const selectedPoint =
    selectedIndex >= 0 ? effectiveData[selectedIndex] : null;

  return (
    <View style={styles.card}>
      {/* Value readout */}
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.totalValue}>
            {selectedPoint ? formatPrice(selectedPoint.value) : "—"}
          </Text>
          {selectedPoint && (
            <Text style={styles.pointLabel}>{selectedPoint.label}</Text>
          )}
        </View>
      </View>

      {/* Chart area */}
      <View style={styles.chartOuter}>
        <View style={styles.chartInner}>
          {effectiveData.map((p, idx) => {
            const norm =
              max === min
                ? 0.5
                : (p.value - min) / (max - min); // 0..1
            const height = 40 + norm * 70; // 40..110
            const isActive = idx === selectedIndex;

            return (
              <Pressable
                key={idx}
                style={styles.segmentPressable}
                onPress={() => setHoverIndex(idx)}
                accessibilityRole="button"
                accessibilityLabel={`${p.label}, ${formatPrice(p.value)}`}
              >
                <View style={styles.segmentColumn}>
                  <View
                    style={[
                      styles.segmentBar,
                      {
                        height,
                        opacity: isActive ? 1 : 0.35,
                      },
                    ]}
                  />
                  <View
                    style={[
                      styles.segmentDot,
                      isActive && styles.segmentDotActive,
                    ]}
                  />
                </View>
                <Text style={styles.tickLabel}>
                  {p.label}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginTop: 8,
    marginBottom: 12,
    // soft shadow
    shadowColor: "#000",
    shadowOpacity: 0.04,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 3 },
    elevation: 1,
  },
  headerRow: {
    marginBottom: 8,
  },
  totalValue: {
    fontSize: 22,
    fontWeight: "700",
  },
  pointLabel: {
    fontSize: 12,
    opacity: 0.7,
    marginTop: 2,
  },
  chartOuter: {
    marginTop: 4,
  },
  chartInner: {
    flexDirection: "row",
    alignItems: "flex-end",
    height: 140,
    paddingHorizontal: 4,
  },
  segmentPressable: {
    flex: 1,
    alignItems: "center",
    justifyContent: "flex-end",
  },
  segmentColumn: {
    alignItems: "center",
    justifyContent: "flex-end",
    marginBottom: 4,
  },
  segmentBar: {
    width: 6,
    borderRadius: 999,
    backgroundColor: "#14B8A6",
  },
  segmentDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#E0F2F1",
    marginTop: 4,
  },
  segmentDotActive: {
    backgroundColor: "#14B8A6",
  },
  tickLabel: {
    fontSize: 9,
    opacity: 0.65,
  },
});
