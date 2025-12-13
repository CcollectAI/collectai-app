import React from "react";
import { View, Text } from "react-native";

interface Props {
  q10: number;
  q50: number;
  q90: number;
}

export default function PredictionBand({ q10, q50, q90 }: Props) {
  return (
    <View
      style={{
        backgroundColor: "white",
        padding: 12,
        borderRadius: 8,
        marginTop: 16,
        marginBottom: 12,
      }}
    >
      <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 8 }}>
        Prediction Range
      </Text>

      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <View>
          <Text style={{ fontSize: 12, color: "#666" }}>Low (q10)</Text>
          <Text style={{ fontSize: 14 }}>€{q10.toFixed(2)}</Text>
        </View>

        <View>
          <Text style={{ fontSize: 12, color: "#666" }}>Median (q50)</Text>
          <Text style={{ fontSize: 14, fontWeight: "600" }}>€{q50.toFixed(2)}</Text>
        </View>

        <View>
          <Text style={{ fontSize: 12, color: "#666" }}>High (q90)</Text>
          <Text style={{ fontSize: 14 }}>€{q90.toFixed(2)}</Text>
        </View>
      </View>
    </View>
  );
}
