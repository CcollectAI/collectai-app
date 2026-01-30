import React, { useEffect, useState } from "react";
import {
  ScrollView,
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { dataProvider, type AnalyticsMetrics } from "@/data";
import { useAppTheme } from "@/hooks/useAppTheme";

type LoadState = "idle" | "loading" | "loaded" | "error";

// Compatibility: replace old ./ui/theme usage with app theme hook
const useAppColors = () => {
  const { colors } = useAppTheme();
  return colors;
};

const initialMetrics: AnalyticsMetrics = {
  activeProjects: 0,
  backlogProjects: 0,
  completedProjects: 0,
  totalBuildMinutes: 0,
  totalBuildHours: 0,
  twitchCreatorsTracked: 0,
  twitchCreatorsLive: 0,
};

const AnalyticsScreen: React.FC = () => {
  const colors = useAppColors();

  const [state, setState] = useState<LoadState>("idle");
  const [errorText, setErrorText] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<AnalyticsMetrics>(initialMetrics);

  useEffect(() => {
    const load = async () => {
      setState("loading");
      setErrorText(null);

      try {
        const data = await dataProvider.getAnalyticsMetrics();
        setMetrics(data);
        setState("loaded");
      } catch (err: any) {
        console.warn("[Analytics] Error loading metrics:", err);
        setState("error");
        setErrorText(err?.message || "Failed to load analytics data.");
      }
    };

    load();
  }, []);

  const bannerLabel =
    state === "loading"
      ? "Loading analytics…"
      : state === "error"
      ? "Analytics unavailable"
      : "Analytics loaded";

  const totalProjects =
    metrics.activeProjects +
    metrics.backlogProjects +
    metrics.completedProjects;

  return (
    <SafeAreaView
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
              Analytics
            </Text>
            <Text style={[styles.headerTitle, { color: colors.text }]}>
              Collection analytics
            </Text>
            <Text style={[styles.headerSub, { color: colors.muted }]}>
              A high-level view for investors and collectors: build progress,
              total hobby time, and Twitch presence, powered by Supabase.
            </Text>
          </View>
          <View style={styles.headerIcon}>
            <Ionicons name="stats-chart-outline" size={20} color={colors.accent} />
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
              Data is fetched via the DataProvider abstraction. In mock mode,
              deterministic demo data is shown.
            </Text>
            {errorText && (
              <Text
                style={[styles.bannerError, { color: "#D64545" }]}
                numberOfLines={2}
              >
                {errorText}
              </Text>
            )}
          </View>
        </View>

        {/* Build & paint analytics */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.cardHeaderRow}>
            <Text style={[styles.cardTitle, { color: colors.text }]}>
              Build & paint analytics
            </Text>
            <Text style={[styles.cardHint, { color: colors.muted }]}>
              Pulled from build_paint_projects + build_paint_sessions
            </Text>
          </View>

          <View style={styles.metricsRow}>
            <View style={styles.metricBlock}>
              <Text style={[styles.metricLabel, { color: colors.muted }]}>
                Active projects
              </Text>
              <Text style={[styles.metricValue, { color: colors.text }]}>
                {metrics.activeProjects}
              </Text>
            </View>
            <View style={styles.metricBlock}>
              <Text style={[styles.metricLabel, { color: colors.muted }]}>
                Backlog
              </Text>
              <Text style={[styles.metricValue, { color: colors.text }]}>
                {metrics.backlogProjects}
              </Text>
            </View>
            <View style={styles.metricBlock}>
              <Text style={[styles.metricLabel, { color: colors.muted }]}>
                Completed
              </Text>
              <Text
                style={[
                  styles.metricValue,
                  { color: metrics.completedProjects > 0 ? "#0BA86C" : colors.text },
                ]}
              >
                {metrics.completedProjects}
              </Text>
            </View>
          </View>

          <View style={styles.metricsRow}>
            <View style={styles.metricBlockWide}>
              <Text style={[styles.metricLabel, { color: colors.muted }]}>
                Total build time (all sessions)
              </Text>
              <Text style={[styles.metricValue, { color: colors.text }]}>
                {metrics.totalBuildMinutes.toLocaleString("en-US")} min
                {"  "}
                <Text style={styles.metricValueSub}>
                  (~{metrics.totalBuildHours.toFixed(1)} hours)
                </Text>
              </Text>
            </View>
          </View>

          <View style={styles.metaRow}>
            <Ionicons
              name="information-circle-outline"
              size={14}
              color={colors.muted}
              style={{ marginRight: 4 }}
            />
            <Text style={[styles.metaText, { color: colors.muted }]}>
              These numbers update when you log time on the Build & paint
              projects screen.
            </Text>
          </View>
        </View>

        {/* Twitch & live content */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.cardHeaderRow}>
            <Text style={[styles.cardTitle, { color: colors.text }]}>
              Twitch & live content
            </Text>
            <Text style={[styles.cardHint, { color: colors.muted }]}>
              Pulled from twitch_creators
            </Text>
          </View>

          <View style={styles.metricsRow}>
            <View style={styles.metricBlock}>
              <Text style={[styles.metricLabel, { color: colors.muted }]}>
                Creators tracked
              </Text>
              <Text style={[styles.metricValue, { color: colors.text }]}>
                {metrics.twitchCreatorsTracked}
              </Text>
            </View>
            <View style={styles.metricBlock}>
              <Text style={[styles.metricLabel, { color: colors.muted }]}>
                Live right now
              </Text>
              <Text style={[styles.metricValue, { color: "#0BA86C" }]}>
                {metrics.twitchCreatorsLive}
              </Text>
            </View>
          </View>

          <View style={styles.metaRow}>
            <Ionicons
              name="logo-twitch"
              size={14}
              color={colors.muted}
              style={{ marginRight: 4 }}
            />
            <Text style={[styles.metaText, { color: colors.muted }]}>
              Hook a worker into the Twitch API to refresh this table. The app
              doesn&apos;t need API keys – it only reads from Supabase.
            </Text>
          </View>
        </View>

        {/* Future analytics placeholder */}
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
          <View style={styles.cardHeaderRow}>
            <Text style={[styles.cardTitle, { color: colors.text }]}>
              Future analytics
            </Text>
          </View>
          <Text style={[styles.futureText, { color: colors.muted }]}>
            Later we can add:
          </Text>
          <Text style={[styles.futureText, { color: colors.muted }]}>
            • Portfolio value over time (once items/prices are in Supabase)
          </Text>
          <Text style={[styles.futureText, { color: colors.muted }]}>
            • Category-level performance (TCG vs. models vs. designer toys)
          </Text>
          <Text style={[styles.futureText, { color: colors.muted }]}>
            • Risk / exposure metrics (e.g. % in sealed vs. loose)
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
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
    maxWidth: 280,
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
  cardHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: "600",
  },
  cardHint: {
    fontSize: 11,
  },
  metricsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 6,
  },
  metricBlock: {
    flex: 1,
    marginRight: 8,
  },
  metricBlockWide: {
    flex: 1,
    marginTop: 4,
  },
  metricLabel: {
    fontSize: 12,
  },
  metricValue: {
    fontSize: 18,
    fontWeight: "700",
    marginTop: 2,
  },
  metricValueSub: {
    fontSize: 12,
    fontWeight: "500",
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 10,
  },
  metaText: {
    fontSize: 11,
    flex: 1,
  },
  futureText: {
    fontSize: 12,
    marginTop: 2,
  },
});

export default AnalyticsScreen;
