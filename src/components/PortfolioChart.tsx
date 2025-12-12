import React from "react";
import { View, Text } from "react-native";
import { theme } from "@/theme";

// Loose props type so whatever Home.tsx passes is accepted
type Props = any;

/**
 * Minimal placeholder portfolio chart.
 * We can later upgrade this to the full fancy line chart,
 * but for now it lets the Home screen render without breaking.
 */
export default function PortfolioChart(_props: Props) {
  return (
    <View
      style={{
        backgroundColor: theme.colors.card,
        borderRadius: 12,
        padding: theme.spacing.md,
        borderWidth: 1,
        borderColor: theme.colors.border,
      }}
    >
      <Text
        style={{
          fontSize: 14,
          fontWeight: "600",
          color: theme.colors.text,
          marginBottom: theme.spacing.xs,
        }}
      >
        Collection value
      </Text>
      <View
        style={{
          height: 140,
          borderRadius: 8,
          borderWidth: 1,
          borderStyle: "dashed",
          borderColor: theme.colors.border,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>
          Chart placeholder (PortfolioChart)
        </Text>
      </View>
    </View>
  );
}
