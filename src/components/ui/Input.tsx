import React from "react";
import { TextInput, View, Text, TextInputProps } from "react-native";
import { color, radius, space } from "../../theme/tokens";
export default function Input({ label, error, style, ...props }:
  TextInputProps & { label?: string; error?: string }
) {
  return (
    <View style={{ gap: space.xs }}>
      {label ? <Text style={{ fontWeight: "600" }}>{label}</Text> : null}
      <TextInput {...props} style={[{
        borderWidth: 1, borderColor: error ? "#ef4444" : color.border,
        borderRadius: radius.md, paddingHorizontal: space.lg, paddingVertical: space.md, backgroundColor: color.bg,
      }, style]} />
      {error ? <Text style={{ color: "#ef4444" }}>{error}</Text> : null}
    </View>
  );
}
