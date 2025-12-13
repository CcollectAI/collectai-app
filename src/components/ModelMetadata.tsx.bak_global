import React from "react";
import { View, Text } from "react-native";

export default function ModelMetadata({
  model = "collectai-v0",
  updated = "Unknown",
  confidence = 0.85,
}) {
  return (
    <View
      style={{
        marginTop: 12,
        backgroundColor: "white",
        padding: 12,
        borderRadius: 8,
        marginBottom: 20,
      }}
    >
      <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 8 }}>
        Model Details
      </Text>

      <Text style={{ fontSize: 14, marginBottom: 4 }}>
        Model: {model}
      </Text>
      <Text style={{ fontSize: 14, marginBottom: 4 }}>
        Confidence score: {(confidence * 100).toFixed(1)}%
      </Text>
      <Text style={{ fontSize: 14 }}>
        Updated: {updated}
      </Text>
    </View>
  );
}
