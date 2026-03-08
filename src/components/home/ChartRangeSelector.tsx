/**
 * Chart time-range pill selector.
 *
 * Row of selectable range pills (1D, 7D, 30D, 90D, 1Y, ALL).
 * Extracted from app/(tabs)/index.tsx.
 */
import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";

// ── Props ──────────────────────────────────────────────────────────────

interface ChartRangeSelectorProps {
  theme: {
    text: string;
    muted: string;
    card: string;
    border: string;
    accent: string;
  };
  selectedRange: string;
  ranges: string[];
  onRangeChange: (range: string) => void;
  hapticsEnabled?: boolean;
}

// ── Component ──────────────────────────────────────────────────────────

function ChartRangeSelectorInner({
  theme,
  selectedRange,
  ranges,
  onRangeChange,
  hapticsEnabled = true,
}: ChartRangeSelectorProps) {
  return (
    <View style={s.rangeRow}>
      {ranges.map((k) => {
        const active = k === selectedRange;
        return (
          <AnimatedPressable
            key={k}
            accessibilityRole="button"
            accessibilityLabel={`Show ${k} range`}
            accessibilityState={{ selected: active }}
            onPress={() => {
              if (k !== selectedRange) {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
              }
              onRangeChange(k);
            }}
            style={[
              s.rangeBtn,
              { backgroundColor: theme.card, borderColor: theme.border },
              active && { backgroundColor: theme.accent + "20", borderColor: theme.accent },
            ]}
          >
            <Text style={[s.rangeText, { color: theme.muted }, active && { color: theme.text }]}>
              {k}
            </Text>
          </AnimatedPressable>
        );
      })}
    </View>
  );
}

export const ChartRangeSelector = React.memo(ChartRangeSelectorInner);

// ── Styles ─────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  rangeRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 8,
    marginBottom: 12,
  },
  rangeBtn: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderWidth: 1,
    borderRadius: 8,
  },
  rangeText: {
    fontWeight: "700",
    fontSize: 13,
  },
});
