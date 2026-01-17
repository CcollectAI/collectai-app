import React from "react";
import { SafeAreaView, View, Text, StyleSheet, Pressable, ScrollView } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";

// Use the SAME theme hook used across the app.
// IMPORTANT: call hooks only at the top-level (no useMemo wrappers).
import { useAppTheme } from "@/theme";

export default function TwitchScreen() {
  const router = useRouter();
  const { colors, radius, spacing } = useAppTheme();

  const s = makeStyles(colors, radius, spacing);

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView contentContainerStyle={s.container} showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={s.headerRow}>
          <View style={{ flex: 1 }}>
            <Text style={s.kicker}>Twitch</Text>
            <Text style={s.title}>Community hub</Text>
            <Text style={s.sub}>
              Track creator streams, drops, and community events. Jump into the leaderboard or events calendar.
            </Text>
          </View>

          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Back"
            onPress={() => router.back()}
            style={s.iconBtn}
          >
            <Ionicons name="chevron-back" size={18} color={colors.text} />
          </Pressable>
        </View>

        {/* Primary actions */}
        <View style={s.actionsRow}>
          <Pressable style={s.actionCard} onPress={() => router.push("/twitch-leaderboard")}>
            <View style={s.actionIcon}>
              <Ionicons name="logo-twitch" size={18} color={colors.accent} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.actionTitle}>Scoreboard</Text>
              <Text style={s.actionSub}>Live creators, ranks, and community stats.</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.muted} />
          </Pressable>

          <Pressable style={s.actionCard} onPress={() => router.push("/events-and-drops")}>
            <View style={s.actionIcon}>
              <Ionicons name="calendar-outline" size={18} color={colors.accent} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.actionTitle}>Events & drops</Text>
              <Text style={s.actionSub}>Upcoming streams, drops and reminders.</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.muted} />
          </Pressable>

          <Pressable style={s.actionCard} onPress={() => router.push("/analytics")}>
            <View style={s.actionIcon}>
              <Ionicons name="stats-chart-outline" size={18} color={colors.accent} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.actionTitle}>Collection analytics</Text>
              <Text style={s.actionSub}>High-level investor view & activity metrics.</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.muted} />
          </Pressable>
        </View>

        {/* Hub sections */}
        <View style={s.sectionRow}>
          <Text style={s.sectionTitle}>What’s happening</Text>
        </View>

        <View style={s.card}>
          <View style={s.cardHeaderRow}>
            <Text style={s.cardTitle}>Live right now</Text>
            <View style={s.pill}>
              <Ionicons name="radio-outline" size={14} color={colors.accent} />
              <Text style={s.pillText}>Live</Text>
            </View>
          </View>
          <Text style={s.cardBody}>
            This section is ready for “who’s live” + quick join actions. We’ll wire it to the Twitch creators table next.
          </Text>
        </View>

        <View style={s.card}>
          <View style={s.cardHeaderRow}>
            <Text style={s.cardTitle}>Creators & banner</Text>
            <Ionicons name="people-outline" size={16} color={colors.muted} />
          </View>
          <Text style={s.cardBody}>
            Put the “featured creator” banner here (instead of cluttering Portfolio). Include stream schedule + drops + top clips.
          </Text>
        </View>

        <View style={{ height: 18 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function makeStyles(colors: any, radius: any, spacing: any) {
  const R = radius?.md ?? 12;
  const P = spacing?.md ?? 16;

  return StyleSheet.create({
    safe: { flex: 1, backgroundColor: colors.background },
    container: { padding: P, paddingBottom: 22 },

    headerRow: {
      flexDirection: "row",
      alignItems: "flex-start",
      justifyContent: "space-between",
      gap: 12,
      marginBottom: 12,
    },
    kicker: { fontSize: 12, fontWeight: "600", color: colors.muted, marginBottom: 2 },
    title: { fontSize: 20, fontWeight: "700", color: colors.text, marginBottom: 4 },
    sub: { fontSize: 12, fontWeight: "500", color: colors.muted, lineHeight: 18 },

    iconBtn: {
      width: 36,
      height: 36,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: colors.card,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radius?.sm ?? 10,
    },

    actionsRow: { gap: 10, marginTop: 6, marginBottom: 14 },
    actionCard: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      padding: 12,
      backgroundColor: colors.card,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: R,
    },
    actionIcon: {
      width: 34,
      height: 34,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: colors.inputBackground ?? colors.card,
      borderWidth: 1,
      borderColor: colors.inputBorder ?? colors.border,
      borderRadius: radius?.sm ?? 10,
    },
    actionTitle: { fontSize: 14, fontWeight: "700", color: colors.text },
    actionSub: { fontSize: 12, fontWeight: "500", color: colors.muted, marginTop: 2 },

    sectionRow: { marginTop: 6, marginBottom: 10 },
    sectionTitle: { fontSize: 14, fontWeight: "700", color: colors.text },

    card: {
      backgroundColor: colors.card,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: R,
      padding: 14,
      marginBottom: 12,
    },
    cardHeaderRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 8,
    },
    cardTitle: { fontSize: 14, fontWeight: "700", color: colors.text },
    cardBody: { fontSize: 12, fontWeight: "500", color: colors.muted, lineHeight: 18 },

    pill: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      paddingHorizontal: 10,
      paddingVertical: 6,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: 999,
      backgroundColor: colors.inputBackground ?? colors.card,
    },
    pillText: { fontSize: 12, fontWeight: "600", color: colors.text },
  });
}
