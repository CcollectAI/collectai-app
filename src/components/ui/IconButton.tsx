import React from "react";
import { Pressable, ViewStyle } from "react-native";
import { radius, space } from "../../theme/tokens";
import { fireHaptic, HapticIntent } from "@/haptics";
export default function IconButton({ children, onPress, style, accessibilityLabel }:{
  children: React.ReactNode; onPress?: ()=>void; style?: ViewStyle; accessibilityLabel?: string;
}) {
  const handlePress = () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    onPress?.();
  };
  return (
    <Pressable onPress={handlePress} hitSlop={10} accessibilityRole="button" accessibilityLabel={accessibilityLabel} style={[{
      paddingHorizontal: space.lg, paddingVertical: space.sm, borderRadius: radius.md,
    }, style]}>
      {children}
    </Pressable>
  );
}
