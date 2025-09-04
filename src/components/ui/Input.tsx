import React from "react";
import { TextInput, View, Text, TextInputProps } from "react-native";

type Props = TextInputProps & { label?: string; error?: string };
export default function Input({ label, error, style, ...props }: Props) {
  return (
    <View style={{ gap: 6 }}>
      {label ? <Text style={{ fontWeight: "600" }}>{label}</Text> : null}
      <TextInput
        {...props}
        style={[
          {
            borderWidth: 1,
            borderColor: error ? "#ef4444" : "#e5e7eb",
            borderRadius: 10,
            paddingHorizontal: 12,
            paddingVertical: 12,
            backgroundColor: "#fff",
          },
          style,
        ]}
      />
      {error ? <Text style={{ color: "#ef4444" }}>{error}</Text> : null}
    </View>
  );
}
