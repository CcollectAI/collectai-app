import React from "react";
import { Pressable, Text, ViewStyle } from "react-native";

type Props = {
  title: string;
  onPress?: () => void;
  disabled?: boolean;
  style?: ViewStyle;
};
export default function Button({ title, onPress, disabled, style }: Props) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={[
        {
          paddingVertical: 14,
          paddingHorizontal: 16,
          borderRadius: 12,
          backgroundColor: disabled ? "#d1d5db" : "#111827",
          alignItems: "center",
        },
        style,
      ]}
    >
      <Text style={{ color: "#fff", fontWeight: "700", fontSize: 16 }}>{title}</Text>
    </Pressable>
  );
}
