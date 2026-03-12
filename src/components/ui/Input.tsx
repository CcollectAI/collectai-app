import React from "react";
import { TextInput, View, Text, TextInputProps } from "react-native";
import { color, radius, space } from "../../theme/tokens";

const DANGER = color.danger;

export default function Input({ label, error, style, ...props }:
  TextInputProps & { label?: string; error?: string }
) {
  return (
    <View style={{ gap: space.xs }}>
      {label ? <Text style={{ fontWeight: "600" }}>{label}</Text> : null}
      <TextInput {...props} accessibilityLabel={label || props.placeholder} style={[{
        borderWidth: 1, borderColor: error ? DANGER : color.border,
        borderRadius: radius.md, paddingHorizontal: space.lg, paddingVertical: space.md, backgroundColor: color.bg,
      }, style]} />
      {error ? <Text style={{ color: DANGER }}>{error}</Text> : null}
    </View>
  );
}
