import React, { useEffect, useMemo, useState } from "react";
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  Image,
} from "react-native";

function ComingSoonScreen() {
  const { colors } = useAppTheme();
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background, padding: 32 }}>
      <Ionicons name="construct-outline" size={48} color={colors.muted} />
      <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, marginTop: 16 }}>Coming Soon</Text>
      <Text style={{ fontSize: 14, color: colors.muted, textAlign: 'center', marginTop: 8, lineHeight: 20 }}>
        This feature is under development. Check back in the next update.
      </Text>
    </View>
  );
}
import { Ionicons } from "@expo/vector-icons";
import { supabase } from "@/lib/supabase";
import { useAppTheme } from "@/hooks/useAppTheme";
import { formatPrice, formatNumber } from "@/lib/format";
type LoadState = "idle" | "loading" | "loaded" | "error";

// Compatibility: replace old ./ui/theme usage with app theme hook
const useAppColors = () => {
  const { colors } = useAppTheme();
  return colors;
};

type TwitchCreator = {
  id: string;
  twitch_login: string;
  display_name: string;
  avatar_url: string | null;
  category: string | null;
  is_partner: boolean;
  is_live: boolean;
  current_title: string | null;
  current_viewers: number | null;
  last_streamed_at: string | null;
  hours_streamed_30d: number | null;
  avg_viewers_30d: number | null;
  max_viewers_30d: number | null;
  followers_gained_30d: number | null;
  revenue_est_30d: number | null;
  score_30d: number | null;
};

const TwitchLeaderboardScreen: React.FC = () => {
  const colors = useAppColors();

  const [state, setState] = useState<LoadState>("idle");
  const [errorText, setErrorText] = useState<string | null>(null);
  const [creators, setCreators] = useState<TwitchCreator[]>([]);

  useEffect(() => {
    const load = async () => {
      setState("loading");
      setErrorText(null);

      try {
        if (!supabase || typeof supabase.from !== "function") {
          setState("error");
          setErrorText(
            "Supabase client not configured – Twitch leaderboard is running in demo mode."
          );
          return;
        }

        const { data, error } = await supabase
          .from("twitch_creators")
          .select("*")
          .order("score_30d", { ascending: false })
          .limit(100);

        if (error) {
          setState("error");
          setErrorText(error.message ?? "Supabase error while loading Twitch data.");
          return;
        }

        setCreators((data ?? []) as TwitchCreator[]);
        setState("loaded");
      } catch (err: unknown) {
        setState("error");
        setErrorText(
          err?.message || "Unexpected error while loading Twitch leaderboard."
        );
      }
    };

    load();
  }, []);

  const liveNow = useMemo(
    () =>
      creators.filter((c) => c.is_live).sort((a, b) => {
        const av = b.current_viewers ?? 0;
        const bv = a.current_viewers ?? 0;
        return av - bv;
      }),
    [creators]
  );

  const leaderboard = useMemo(
    () =>
      creators
        .slice()
        .sort((a, b) => (b.score_30d ?? 0) - (a.score_30d ?? 0)),
    [creators]
  );

  const totalCreators = creators.length;
  const liveCount = liveNow.length;

  const bannerLabel =
    state === "loading"
      ? "Loading Twitch creators from Supabase…"
      : state === "error"
      ? "Twitch stats running in demo mode"
      : "Twitch leaderboard synced with Supabase";

  return (
    <View
      style={[styles.safeArea, { backgroundColor: colors.background }]}
    >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
      >
        {/* Header */}
        <View style={styles.headerRow}>
          <View>
            <Text style={[styles.headerLabel, { color: colors.muted }]}>
              Twitch
            </Text>
            <Text style={[styles.headerTitle, { color: colors.text }]}>
              Twitch leaderboard
            </Text>
            <Text style={[styles.headerSub, { color: colors.muted }]}>
              Track streamers who build, paint and break boxes live. Wired for
              Supabase so you can plug in the Twitch API later.
            </Text>
          </View>
          <View style={styles.headerIcon}>
            <Ionicons
              name="logo-twitch"
              size={20}
              color={colors.accent}
            />
          </View>
        </View>

        {/* Status banner */}
        <View
          style={[
            styles.banner,
            {
              backgroundColor:
                state === "error"
                  ? "#FDECEC"
                  : state === "loading"
                  ? "#FFF7E6"
                  : "#E7F6F8",
              borderColor:
                state === "error"
                  ? "#D64545"
                  : state === "loading"
                  ? "#F59E0B"
                  : "#19A7AE",
            },
          ]}
        >
          <View style={styles.bannerIconBox}>
            {state === "loading" ? (
              <ActivityIndicator size="small" color={colors.accent} />
            ) : (
              <Ionicons
                name={
                  state === "error"
                    ? "warning-outline"
                    : "checkmark-circle-outline"
                }
                size={18}
                color={
                  state === "error"
                    ? "#D64545"
                    : "#19A7AE"
                }
              />
            )}
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[styles.bannerTitle, { color: colors.text }]}>
              {bannerLabel}
            </Text>
            <Text style={[styles.bannerBody, { color: colors.muted }]}>
              Feed this table from a small worker that calls the Twitch API
              (Helix). The app only reads from Supabase, so it stays simple and
              stable.
            </Text>
            {errorText ? (
              <Text
                style={[styles.bannerError, { color: "#D64545" }]}
                numberOfLines={2}
              >
                {errorText}
              </Text>
            ) : null}
          </View>
        </View>

        {/* Summary card */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.summaryRow}>
            <View style={styles.summaryBlock}>
              <Text style={[styles.summaryLabel, { color: colors.muted }]}>
                Creators tracked
              </Text>
              <Text style={[styles.summaryValue, { color: colors.text }]}>
                {totalCreators}
              </Text>
            </View>
            <View style={styles.summaryBlock}>
              <Text style={[styles.summaryLabel, { color: colors.muted }]}>
                Live now
              </Text>
              <Text style={[styles.summaryValue, { color: "#0BA86C" }]}>
                {liveCount}
              </Text>
            </View>
          </View>
          <View style={styles.summaryRow}>
            <View style={styles.summaryBlock}>
              <Text style={[styles.summaryLabel, { color: colors.muted }]}>
                Top metric
              </Text>
              <Text style={[styles.summaryValueSmall, { color: colors.muted }]}>
                score_30d · formula you define later
              </Text>
            </View>
          </View>
        </View>

        {/* Live now section */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.sectionHeaderRow}>
            <View style={styles.sectionHeaderLeft}>
              <View style={styles.liveDot} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>
                Live now
              </Text>
            </View>
            <Text style={[styles.sectionHint, { color: colors.muted }]}>
              Top 3 by current viewers
            </Text>
          </View>

          {liveNow.length === 0 ? (
            <Text style={[styles.emptyText, { color: colors.muted }]}>
              No one is live right now. Once your worker flags creators as
              is_live = true, they&apos;ll show here.
            </Text>
          ) : (
            liveNow.slice(0, 3).map((c) => (
              <View key={c.id} style={styles.liveRow}>
                <View style={styles.avatarWrapper}>
                  {c.avatar_url ? (
                    <Image
                      source={{ uri: c.avatar_url }}
                      style={styles.avatar}
                    />
                  ) : (
                    <View style={styles.avatarFallback}>
                      <Ionicons
                        name="person-circle-outline"
                        size={24}
                        color={colors.muted}
                      />
                    </View>
                  )}
                </View>
                <View style={{ flex: 1 }}>
                  <Text
                    style={[styles.creatorName, { color: colors.text }]}
                    numberOfLines={1}
                  >
                    {c.display_name}
                  </Text>
                  <Text
                    style={[styles.creatorMeta, { color: colors.muted }]}
                    numberOfLines={1}
                  >
                    {c.category || "Collectors / Mixed"} ·{" "}
                    {c.current_title || "Live now"}
                  </Text>
                </View>
                <View style={styles.liveRight}>
                  <View style={styles.viewerPill}>
                    <Ionicons
                      name="eye-outline"
                      size={12}
                      color="#D64545"
                      style={{ marginRight: 4 }}
                    />
                    <Text style={styles.viewerPillText}>
                      {c.current_viewers ?? 0}
                    </Text>
                  </View>
                  {c.is_partner && (
                    <Text style={styles.partnerTag}>Partner</Text>
                  )}
                </View>
              </View>
            ))
          )}
        </View>

        {/* 30-day leaderboard */}
        <View
          style={[
            styles.card,
            {
              backgroundColor: colors.card,
              borderColor: colors.border,
              marginBottom: 24,
            },
          ]}
        >
          <View style={styles.sectionHeaderRow}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>
              30-day leaderboard
            </Text>
            <Text style={[styles.sectionHint, { color: colors.muted }]}>
              Sorted by score_30d
            </Text>
          </View>

          {leaderboard.length === 0 ? (
            <Text style={[styles.emptyText, { color: colors.muted }]}>
              No Twitch creators found. Add rows to the twitch_creators table in
              Supabase to see this leaderboard come alive.
            </Text>
          ) : (
            leaderboard.map((c, idx) => (
              <View key={c.id}>
                <View style={styles.rankRow}>
                  {/* Rank + badge */}
                  <View style={styles.rankBadge}>
                    <Text style={styles.rankText}>{idx + 1}</Text>
                  </View>

                  {/* Creator info */}
                  <View style={styles.rankMain}>
                    <Text
                      style={[styles.creatorName, { color: colors.text }]}
                      numberOfLines={1}
                    >
                      {c.display_name}
                    </Text>
                    <Text
                      style={[styles.creatorMeta, { color: colors.muted }]}
                      numberOfLines={1}
                    >
                      {c.category || "Collectors / Mixed"} ·{" "}
                      {c.twitch_login}
                    </Text>

                    <View style={styles.rankMetricsRow}>
                      <View style={styles.rankMetric}>
                        <Text
                          style={[
                            styles.metricLabel,
                            { color: colors.muted },
                          ]}
                        >
                          Hours 30d
                        </Text>
                        <Text
                          style={[
                            styles.metricValue,
                            { color: colors.text },
                          ]}
                        >
                          {formatNumber(c.hours_streamed_30d)}
                        </Text>
                      </View>
                      <View style={styles.rankMetric}>
                        <Text
                          style={[
                            styles.metricLabel,
                            { color: colors.muted },
                          ]}
                        >
                          Avg viewers
                        </Text>
                        <Text
                          style={[
                            styles.metricValue,
                            { color: colors.text },
                          ]}
                        >
                          {formatNumber(c.avg_viewers_30d)}
                        </Text>
                      </View>
                      <View style={styles.rankMetric}>
                        <Text
                          style={[
                            styles.metricLabel,
                            { color: colors.muted },
                          ]}
                        >
                          Est. rev
                        </Text>
                        <Text
                          style={[
                            styles.metricValue,
                            { color: colors.text },
                          ]}
                        >
                          {formatPrice(c.revenue_est_30d)}
                        </Text>
                      </View>
                    </View>
                  </View>

                  {/* Score pill */}
                  <View style={styles.scorePill}>
                    <Text style={styles.scoreLabel}>Score</Text>
                    <Text style={styles.scoreValue}>
                      {formatNumber(c.score_30d)}
                    </Text>
                  </View>
                </View>

                {idx < leaderboard.length - 1 && (
                  <View
                    style={[
                      styles.separator,
                      { backgroundColor: colors.border },
                    ]}
                  />
                )}
              </View>
            ))
          )}
        </View>
      </ScrollView>
      <QuickNavBar />
    </View>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  scroll: { flex: 1 },
  scrollContent: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 16,
  },
  headerLabel: {
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    fontWeight: "600",
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: "700",
    marginTop: 2,
  },
  headerSub: {
    fontSize: 12,
    marginTop: 4,
    maxWidth: 270,
  },
  headerIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#D6E4EC",
  },
  banner: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 16,
  },
  bannerIconBox: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 8,
  },
  bannerTitle: {
    fontSize: 13,
    fontWeight: "600",
  },
  bannerBody: {
    fontSize: 11,
    marginTop: 2,
  },
  bannerError: {
    fontSize: 11,
    marginTop: 2,
  },
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 16,
  },
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  summaryBlock: {
    flex: 1,
    marginRight: 8,
  },
  summaryLabel: {
    fontSize: 12,
  },
  summaryValue: {
    fontSize: 18,
    fontWeight: "700",
    marginTop: 2,
  },
  summaryValueSmall: {
    fontSize: 11,
    marginTop: 4,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  sectionHeaderLeft: {
    flexDirection: "row",
    alignItems: "center",
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "600",
  },
  sectionHint: {
    fontSize: 11,
  },
  liveDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#D64545",
    marginRight: 6,
  },
  emptyText: {
    fontSize: 12,
    marginTop: 4,
  },
  liveRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
  },
  avatarWrapper: {
    marginRight: 8,
  },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
  },
  avatarFallback: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#E7F6F8",
  },
  liveRight: {
    alignItems: "flex-end",
    marginLeft: 8,
  },
  viewerPill: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
    backgroundColor: "#FDECEC",
  },
  viewerPillText: {
    fontSize: 11,
    fontWeight: "600",
    color: "#D64545",
  },
  partnerTag: {
    marginTop: 4,
    fontSize: 11,
    fontWeight: "600",
    color: "#A855F7",
  },
  creatorName: {
    fontSize: 14,
    fontWeight: "600",
  },
  creatorMeta: {
    fontSize: 11,
    marginTop: 2,
  },
  rankRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingVertical: 8,
  },
  rankBadge: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#E7F6F8",
    marginRight: 8,
  },
  rankText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#19A7AE",
  },
  rankMain: {
    flex: 1,
    paddingRight: 8,
  },
  rankMetricsRow: {
    flexDirection: "row",
    marginTop: 4,
  },
  rankMetric: {
    marginRight: 12,
  },
  metricLabel: {
    fontSize: 10,
  },
  metricValue: {
    fontSize: 12,
    fontWeight: "600",
  },
  scorePill: {
    alignItems: "flex-end",
  },
  scoreLabel: {
    fontSize: 10,
    color: "#647589",
  },
  scoreValue: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0C2233",
    marginTop: 2,
  },
  separator: {
    height: StyleSheet.hairlineWidth,
    marginVertical: 6,
  },
});

function TwitchLeaderboardScreenWithBoundary() {
  const Inner = __DEV__ ? TwitchLeaderboardScreen : ComingSoonScreen;
  return (
    <ScreenErrorBoundary screenName="Twitch Leaderboard">
      <Inner />
    </ScreenErrorBoundary>
  );
}

export default TwitchLeaderboardScreenWithBoundary;
