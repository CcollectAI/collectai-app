import React from "react";
import { View, Text, StyleSheet, Animated } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useEnterReveal } from "@/motion";
import { useAppTheme } from "@/hooks/useAppTheme";
import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import { QuickNavBar } from '@/components/QuickNavBar';

function TwitchScreenInner() {
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      <Animated.View style={animatedStyle}>
      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.row}>
          <Ionicons name="logo-twitch" size={18} color={colors.accent} />
          <Text style={[styles.cardTitle, { color: colors.text }]}>Creator & Drops Hub</Text>
        </View>
        <Text style={[styles.cardText, { color: colors.muted }]}>
          This is the Twitch landing page. We'll move the "Twitch creators" banner here and keep Portfolio clean.
        </Text>
      </View>
      </Animated.View>
      <QuickNavBar />
    </SafeAreaView>
  );
}

export default function TwitchScreen() {
  return (
    <ScreenErrorBoundary screenName="Twitch">
      <TwitchScreenInner />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, padding: 16 },
  card: {
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
  },
  row: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 8 },
  cardTitle: { fontSize: 14, fontWeight: "900" },
  cardText: { fontSize: 13, fontWeight: "700", lineHeight: 18 },
});
