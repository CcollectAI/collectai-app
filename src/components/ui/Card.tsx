import React from "react";
import { View, ViewStyle } from "react-native";
import { color, radius, space, shadow } from "../../theme/tokens";
export default function Card({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  return (
    <View style={[{
      backgroundColor: color.bg,
      borderWidth: 1, borderColor: color.border,
      borderRadius: radius.lg, padding: space.lg,
      }, shadow.card, style]}>
      {children}
    </View>
  );
}
