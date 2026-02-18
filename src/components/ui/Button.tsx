import React from "react";
import { Pressable, Text, ViewStyle } from "react-native";
import { color, radius, space, text as T } from "../../theme/tokens";
import { fireHaptic, HapticIntent } from "@/haptics";
export default function Button({ title, onPress, disabled, style }:{
  title:string; onPress?:()=>void; disabled?:boolean; style?:ViewStyle
}) {
  const handlePress = () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    onPress?.();
  };
  return (
    <Pressable onPress={handlePress} disabled={disabled} accessibilityRole="button" accessibilityLabel={title} style={[{
      backgroundColor: disabled ? "#d1d5db" : color.brand.base,
      paddingVertical: space.md, paddingHorizontal: space.lg,
      borderRadius: radius.md, alignItems: "center",
    }, style]}>
      <Text style={{ color: "#fff", fontWeight: "700", fontSize: T.lg }}>{title}</Text>
    </Pressable>
  );
}
