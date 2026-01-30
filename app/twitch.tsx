import React from "react";
import { View, Text, StyleSheet, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";

export default function TwitchScreen() {
  const router = useRouter();

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>Twitch Overview</Text>
        <Pressable onPress={() => router.back()} style={styles.iconBtn} accessibilityLabel="Back">
          <Ionicons name="chevron-back" size={18} color="#0b1f3a" />
        </Pressable>
      </View>

      <View style={styles.card}>
        <View style={styles.row}>
          <Ionicons name="logo-twitch" size={18} color="#14b8a6" />
          <Text style={styles.cardTitle}>Creator & Drops Hub</Text>
        </View>
        <Text style={styles.cardText}>
          This is the Twitch landing page. We’ll move the “Twitch creators” banner here and keep Portfolio clean.
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#f6f7f9", padding: 16 },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 10 },
  title: { fontSize: 18, fontWeight: "900", color: "#0b1f3a" },
  iconBtn: {
    width: 34, height: 34, borderRadius: 17,
    alignItems: "center", justifyContent: "center",
    backgroundColor: "#ffffff",
    borderWidth: 1, borderColor: "rgba(11,31,58,0.08)",
  },
  card: {
    backgroundColor: "#ffffff",
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: "rgba(11,31,58,0.08)",
  },
  row: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 8 },
  cardTitle: { fontSize: 14, fontWeight: "900", color: "#0b1f3a" },
  cardText: { fontSize: 13, fontWeight: "700", color: "rgba(11,31,58,0.72)", lineHeight: 18 },
});
