import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { useLocalSearchParams } from "expo-router";

export default function UserProfileCardScreen() {
  const params = useLocalSearchParams();
  const id = String(params?.id ?? "unknown");
  const name = String(params?.name ?? "Collector");
  const handle = String(params?.handle ?? "@user");
  const city = String(params?.city ?? "Amsterdam");
  const bio = String(params?.bio ?? "Collector. Here for trades + meetups.");

  return (
    <View style={styles.safe}>
      <View style={styles.card}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>{(name?.[0] ?? "C").toUpperCase()}</Text>
        </View>

        <Text style={styles.name} numberOfLines={1}>{name}</Text>
        <Text style={styles.handle} numberOfLines={1}>{handle} • {city}</Text>

        <View style={styles.divider} />

        <Text style={styles.bio}>{bio}</Text>

        <View style={styles.metaRow}>
          <View style={styles.metaPill}><Text style={styles.metaText}>ID: {id}</Text></View>
          <View style={styles.metaPill}><Text style={styles.metaText}>Opted-in</Text></View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: "#FFFFFF",
    padding: 16,
  },
  card: {
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(11,31,58,0.10)",
    padding: 16,
    backgroundColor: "#FFFFFF",
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "rgba(20,184,166,0.18)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 10,
  },
  avatarText: {
    fontWeight: "900",
    fontSize: 18,
    color: "#0b1f3a",
  },
  name: {
    fontSize: 18,
    fontWeight: "900",
    color: "#0b1f3a",
  },
  handle: {
    marginTop: 2,
    fontSize: 12,
    fontWeight: "800",
    color: "#64748b",
  },
  divider: {
    marginTop: 12,
    marginBottom: 12,
    height: 1,
    backgroundColor: "rgba(11,31,58,0.06)",
  },
  bio: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0b1f3a",
    opacity: 0.9,
    lineHeight: 18,
  },
  metaRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 12,
    flexWrap: "wrap",
  },
  metaPill: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: "rgba(11,31,58,0.06)",
  },
  metaText: {
    fontSize: 12,
    fontWeight: "900",
    color: "#0b1f3a",
    opacity: 0.75,
  },
});
