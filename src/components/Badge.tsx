import React from "react";
import { Text, View, ViewStyle, TextStyle } from "react-native";

type Props = {
  children: React.ReactNode;
  style?: ViewStyle;
  textStyle?: TextStyle;
  variant?: "default" | "success" | "warning" | "danger";
};

const COLORS: Record<NonNullable<Props["variant"]>, { bg: string; fg: string; border: string }> = {
  default: { bg: "#f3f4f6", fg: "#111827", border: "#e5e7eb" },
  success: { bg: "#ecfdf5", fg: "#065f46", border: "#a7f3d0" },
  warning: { bg: "#fffbeb", fg: "#92400e", border: "#fcd34d" },
  danger:  { bg: "#fef2f2", fg: "#991b1b", border: "#fecaca" },
};

export default function Badge({ children, style, textStyle, variant = "default" }: Props) {
  const c = COLORS[variant];
  return (
    <View
      style={[
        {
          paddingHorizontal: 8,
          paddingVertical: 4,
          borderRadius: 999,
          backgroundColor: c.bg,
          borderWidth: 1,
          borderColor: c.border,
          alignSelf: "flex-start",
        },
        style,
      ]}
    >
      <Text style={[{ fontSize: 12, fontWeight: "600", color: c.fg }, textStyle]}>{children}</Text>
    </View>
  );
}
