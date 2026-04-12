/**
 * Twitch Landing — Creator & Drops Hub.
 * Shows live creators, recent drops, and links to the full leaderboard.
 */
import React, { useEffect, useState } from "react";
import { View, Text, ScrollView, StyleSheet, Animated, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useEnterReveal , AnimatedPressable } from "@/motion";
import { useAppTheme } from "@/hooks/useAppTheme";
import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import { QuickNavBar } from "@/components/QuickNavBar";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { supabase } from "@/lib/supabase";
import { TWITCH_PURPLE } from "@/constants/colors";

type TwitchStats = {
  liveCount: string;
  creatorsCount: string;
  dropsCount: string;
};

const PLACEHOLDER: TwitchStats = { liveCount: "\u2014", creatorsCount: "\u2014", dropsCount: "\u2014" };

function useTwitchStats(): { stats: TwitchStats; loading: boolean } {
  const [stats, setStats] = useState<TwitchStats>(PLACEHOLDER);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        if (!supabase || typeof supabase.from !== "function") {
          return;
        }

        // Fetch total creators count
        const { count: totalCount, error: totalErr } = await supabase
          .from("twitch_creators")
          .select("id", { count: "exact", head: true });

        if (cancelled) return;
        if (totalErr) return; // table likely doesn't exist

        // Fetch live creators count
        const { count: liveCount, error: liveErr } = await supabase
          .from("twitch_creators")
          .select("id", { count: "exact", head: true })
          .eq("is_live", true);

        if (cancelled) return;

        setStats({
          liveCount: liveErr ? "\u2014" : String(liveCount ?? 0),
          creatorsCount: String(totalCount ?? 0),
          dropsCount: "\u2014", // No drops table yet
        });
      } catch {
        // Table doesn't exist or network error — keep placeholder dashes
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
  }, []);

  return { stats, loading };
}

function TwitchScreenInner() {
  const { colors } = useAppTheme();
  const router = useRouter();
  const { settings } = useSettings();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { stats, loading: statsLoading } = useTwitchStats();

  return (
    <SafeAreaView
      style={[styles.safe, { backgroundColor: colors.background }]}
      edges={["left", "right"]}
    >
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
          {/* Header */}
          <View style={styles.headerRow}>
            <View style={{ flex: 1 }}>
              <Text style={[styles.headerLabel, { color: colors.muted }]}>TWITCH</Text>
              <Text style={[styles.headerTitle, { color: colors.text }]}>
                Creator & Drops Hub
              </Text>
              <Text style={[styles.headerSub, { color: colors.muted }]}>
                Track collectors who stream live unboxings, builds, and grading sessions.
              </Text>
            </View>
            <View
              style={[
                styles.headerIcon,
                { backgroundColor: TWITCH_PURPLE + "15", borderColor: TWITCH_PURPLE + "30" },
              ]}
            >
              <Ionicons name="logo-twitch" size={22} color={TWITCH_PURPLE} />
            </View>
          </View>

          {/* Quick Stats */}
          <View style={[styles.statsRow]}>
            <View style={[styles.statCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Ionicons name="videocam" size={18} color={colors.error} />
              {statsLoading ? (
                <ActivityIndicator size="small" color={colors.muted} style={{ marginVertical: 2 }} />
              ) : (
                <Text style={[styles.statValue, { color: colors.text }]}>{stats.liveCount}</Text>
              )}
              <Text style={[styles.statLabel, { color: colors.muted }]}>Live Streams</Text>
            </View>
            <View style={[styles.statCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Ionicons name="people" size={18} color={colors.accent} />
              {statsLoading ? (
                <ActivityIndicator size="small" color={colors.muted} style={{ marginVertical: 2 }} />
              ) : (
                <Text style={[styles.statValue, { color: colors.text }]}>{stats.creatorsCount}</Text>
              )}
              <Text style={[styles.statLabel, { color: colors.muted }]}>Creators</Text>
            </View>
            <View style={[styles.statCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Ionicons name="gift" size={18} color={TWITCH_PURPLE} />
              {statsLoading ? (
                <ActivityIndicator size="small" color={colors.muted} style={{ marginVertical: 2 }} />
              ) : (
                <Text style={[styles.statValue, { color: colors.text }]}>{stats.dropsCount}</Text>
              )}
              <Text style={[styles.statLabel, { color: colors.muted }]}>Active Drops</Text>
            </View>
          </View>

          {/* Leaderboard Link */}
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              router.push("/twitch-leaderboard");
            }}
            style={[styles.linkCard, { backgroundColor: colors.card, borderColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel="View Twitch creator leaderboard"
          >
            <View style={[styles.linkIconCircle, { backgroundColor: TWITCH_PURPLE + "15" }]}>
              <Ionicons name="trophy" size={20} color={TWITCH_PURPLE} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.linkTitle, { color: colors.text }]}>
                Creator Leaderboard
              </Text>
              <Text style={[styles.linkSub, { color: colors.muted }]}>
                30-day rankings by hours streamed, viewers, and engagement
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.muted} />
          </AnimatedPressable>

          {/* What to Expect */}
          <View style={[styles.sectionCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>
              What You Get
            </Text>
            {[
              { icon: "eye-outline" as const, title: "Live Stream Alerts", desc: "Get notified when top collectors go live" },
              { icon: "cube-outline" as const, title: "Unboxing Drops", desc: "Track exclusive items revealed during streams" },
              { icon: "bar-chart-outline" as const, title: "Viewer Insights", desc: "See which categories draw the most viewers" },
              { icon: "star-outline" as const, title: "Partner Spotlights", desc: "Featured creators with verified collections" },
            ].map((item, i) => (
              <View key={i} style={[styles.featureRow, i > 0 && { borderTopColor: colors.border, borderTopWidth: StyleSheet.hairlineWidth }]}>
                <View style={[styles.featureIcon, { backgroundColor: colors.accent + "10" }]}>
                  <Ionicons name={item.icon} size={16} color={colors.accent} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.featureTitle, { color: colors.text }]}>{item.title}</Text>
                  <Text style={[styles.featureDesc, { color: colors.muted }]}>{item.desc}</Text>
                </View>
              </View>
            ))}
          </View>
        </Animated.View>
      </ScrollView>
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
  safe: { flex: 1 },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 32,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 20,
  },
  headerLabel: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: "700",
    marginTop: 4,
  },
  headerSub: {
    fontSize: 13,
    marginTop: 6,
    lineHeight: 18,
    maxWidth: 260,
  },
  headerIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
  },
  statsRow: {
    flexDirection: "row",
    gap: 10,
    marginBottom: 16,
  },
  statCard: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 14,
    borderRadius: 14,
    borderWidth: 1,
    gap: 4,
  },
  statValue: {
    fontSize: 15,
    fontWeight: "700",
  },
  statLabel: {
    fontSize: 11,
    fontWeight: "500",
  },
  linkCard: {
    flexDirection: "row",
    alignItems: "center",
    padding: 14,
    borderRadius: 16,
    borderWidth: 1,
    marginBottom: 16,
    gap: 12,
  },
  linkIconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  linkTitle: {
    fontSize: 15,
    fontWeight: "700",
  },
  linkSub: {
    fontSize: 12,
    marginTop: 2,
    lineHeight: 16,
  },
  sectionCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "700",
    marginBottom: 12,
  },
  featureRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 12,
  },
  featureIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  featureTitle: {
    fontSize: 14,
    fontWeight: "600",
  },
  featureDesc: {
    fontSize: 12,
    marginTop: 2,
    lineHeight: 16,
  },
});
