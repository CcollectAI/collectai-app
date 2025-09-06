import React from "react";
import { Text, View, ViewStyle, TextStyle } from "react-native";
import { color, radius, space, text as T } from "../theme/tokens";
type Props = { children: React.ReactNode; style?: ViewStyle; textStyle?: TextStyle; variant?: "default" | "success" | "danger" };
const palette = {
  default: { bg: "#f3f4f6", fg: color.text, border: color.border },
  success: { bg: "#ecfdf5", fg: "#065f46", border: "#a7f3d0" },
  danger:  { bg: "#fef2f2", fg: "#991b1b", border: "#fecaca" },
};
export default function Badge({ children, style, textStyle, variant="default" }: Props) {
  const c = palette[variant];
  return (
    <View style={[{
      paddingHorizontal: space.sm, paddingVertical: 4,
      borderRadius: radius.pill, backgroundColor: c.bg, borderWidth:1, borderColor: c.border, alignSelf:"flex-start",
    }, style]}>
      <Text style={[{ fontSize: T.sm, fontWeight:"600", color: c.fg }, textStyle]}>{children}</Text>
    </View>
  );
}
