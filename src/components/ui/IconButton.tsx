import React from "react";
import { Pressable, ViewStyle } from "react-native";
import { radius, space } from "../../theme/tokens";
export default function IconButton({ children, onPress, style }:{
  children: React.ReactNode; onPress?: ()=>void; style?: ViewStyle
}) {
  return (
    <Pressable onPress={onPress} hitSlop={10} accessibilityRole="button" style={[{
      paddingHorizontal: space.lg, paddingVertical: space.sm, borderRadius: radius.md,
    }, style]}>
      {children}
    </Pressable>
  );
}
