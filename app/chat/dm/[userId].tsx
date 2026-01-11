import React, { useMemo, useState } from "react";
import { View, Text, Pressable, StyleSheet, TextInput, ScrollView } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";

import { getUserById } from "@/data/users";

const DARK = {
  BG: "#0f172a",
  CARD: "#020617",
  BORDER: "#1f2933",
  TEXT: "#e5e7eb",
  MUTED: "#9ca3af",
  PRIMARY: "#0ea5e9",
};

function safeDecode(x?: string | string[]) {
  const raw = Array.isArray(x) ? x[0] : x;
  return raw ? decodeURIComponent(String(raw)) : "";
}

export default function DmScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { userId, action } = useLocalSearchParams<{ userId?: string | string[]; action?: string }>();

  const userIdStr = safeDecode(userId);
  const mode = (action ?? "dm").toLowerCase(); // "connect" or "dm"
  const [text, setText] = useState("");

  const user = useMemo(() => (userIdStr ? (getUserById(userIdStr as any) as any) : undefined), [userIdStr]);
  const name = user?.name ?? "Collector";

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: DARK.BG }]} edges={["top", "left", "right"]}>
      <View style={[styles.container, { paddingTop: Math.max(12, insets.top), paddingBottom: 16 }]}>
        <View style={styles.headerRow}>
          <Pressable onPress={() => router.back()} style={[styles.iconBtn, { borderColor: DARK.BORDER }]}>
            <Ionicons name="chevron-back" size={18} color={DARK.MUTED} />
          </Pressable>
          <View style={{ flex: 1, paddingHorizontal: 10 }}>
            <Text style={[styles.headerTitle, { color: DARK.TEXT }]} numberOfLines={1}>
              {mode === "connect" ? "Connect request" : "Chat"}
            </Text>
            <Text style={[styles.headerSub, { color: DARK.MUTED }]} numberOfLines={1}>
              {name}
            </Text>
          </View>
          <View style={{ width: 36 }} />
        </View>

        <View style={[styles.card, { backgroundColor: DARK.CARD, borderColor: DARK.BORDER }]}>
          <Text style={[styles.body, { color: DARK.MUTED }]}>
            {mode === "connect"
              ? "This is a mock Connect flow. Later we’ll store connection requests + open a DM thread after accept."
              : "This is a mock DM screen. Later we’ll back it with Supabase Realtime + RLS."}
          </Text>
        </View>

        <View style={[styles.card, { backgroundColor: DARK.CARD, borderColor: DARK.BORDER, flex: 1 }]}>
          <ScrollView>
            <Text style={[styles.msgMuted, { color: DARK.MUTED }]}>No messages yet.</Text>
          </ScrollView>

          <View style={[styles.composer, { borderColor: DARK.BORDER }]}>
            <TextInput
              value={text}
              onChangeText={setText}
              placeholder={mode === "connect" ? "Write a short connect note…" : "Message…"}
              placeholderTextColor={DARK.MUTED}
              style={[styles.input, { color: DARK.TEXT }]}
            />
            <Pressable
              onPress={() => setText("")}
              style={[styles.sendBtn, { backgroundColor: DARK.PRIMARY }]}
            >
              <Ionicons name="send-outline" size={16} color="#fff" />
            </Pressable>
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  container: { flex: 1, paddingHorizontal: 16 },
  headerRow: { flexDirection: "row", alignItems: "center", marginBottom: 12 },
  iconBtn: { width: 36, height: 36, borderRadius: 999, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  headerTitle: { fontSize: 16, fontWeight: "900" },
  headerSub: { marginTop: 2, fontSize: 11, fontWeight: "600" },

  card: { borderRadius: 16, borderWidth: 1, padding: 12, marginBottom: 10 },
  body: { fontSize: 12, lineHeight: 17, fontWeight: "600" },

  msgMuted: { fontSize: 12, fontWeight: "700" },

  composer: { marginTop: 10, borderWidth: 1, borderRadius: 14, padding: 10, flexDirection: "row", gap: 8, alignItems: "center" },
  input: { flex: 1, fontSize: 12, fontWeight: "700" },
  sendBtn: { width: 38, height: 38, borderRadius: 12, alignItems: "center", justifyContent: "center" },
});
