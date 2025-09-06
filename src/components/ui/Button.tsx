import React from "react";
import { Pressable, Text, ViewStyle } from "react-native";
import { color, radius, space, text as T } from "../../theme/tokens";
export default function Button({ title, onPress, disabled, style }:{
  title:string; onPress?:()=>void; disabled?:boolean; style?:ViewStyle
}) {
  return (
    <Pressable onPress={onPress} disabled={disabled} style={[{
      backgroundColor: disabled ? "#d1d5db" : color.primary,
      paddingVertical: space.md, paddingHorizontal: space.lg,
      borderRadius: radius.md, alignItems: "center",
    }, style]}>
      <Text style={{ color: "#fff", fontWeight: "700", fontSize: T.lg }}>{title}</Text>
    </Pressable>
  );
}
