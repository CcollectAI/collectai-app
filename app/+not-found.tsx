import React from "react";
import { View, Text, Pressable } from "react-native";
import { Link } from "expo-router";

export default function NotFound() {
  return (
    <View style={{ flex: 1, backgroundColor: "#E6F7F8", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <Text style={{ fontSize: 18, fontWeight: "700", color: "#0B3D91", marginBottom: 8 }}>Page not found</Text>
      <Link href="/" asChild>
        <Pressable style={{ paddingHorizontal: 16, paddingVertical: 10, borderWidth: 1, borderColor: "#0B3D91", backgroundColor: "#fff" }}>
          <Text style={{ color: "#0B3D91", fontWeight: "700" }}>Go Home</Text>
        </Pressable>
      </Link>
    </View>
  );
}
