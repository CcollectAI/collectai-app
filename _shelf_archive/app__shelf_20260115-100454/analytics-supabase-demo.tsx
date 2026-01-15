import React, { useEffect, useState } from "react";
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import supabase from "@/lib/supabaseClient";
import { useAppTheme } from "@/hooks/useAppTheme";
type ItemRow = {
  id: string;
  title: string | null;
  category: string | null;
  value: number | null;
};

// Compatibility: replace old ./ui/theme usage with app theme hook
const useAppColors = () => {
  const { colors } = useAppTheme();
  return colors;
};

type CategorySummary = {
  category: string;
  count: number;
  totalValue: number;
};

type LoadState = "idle" | "loading" | "loaded" | "error";

const formatCurrency = (value: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
  }).format(value);

const AnalyticsSupabaseDemo: React.FC = () => {
  const colors = useAppColors();

  const [state, setState] = useState<LoadState>("idle");
  const [items, setItems] = useState<ItemRow[]>([]);
  const [errorText, setErrorText] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setState("loading");
      setErrorText(null);

      try {
        const { data, error } = await supabase
          .from("items")
          .select("id,title,category,value")
          .limit(200);

        if (error) {
          setState("error");
          setErrorText(error.message ?? "Supabase error");
          return;
        }

        setItems((data ?? []) as ItemRow[]);
        setState("loaded");
      } catch (err: any) {
        setState("error");
        setErrorText(
          err?.message || "Unexpected error while fetching from Supabase"
        );
      }
    };

    load();
  }, []);

  const totalItems = items.length;
  const totalValue = items.reduce(
    (sum, item) => sum + (typeof item.value === "number" ? item.value : 0),
    0
  );

  const byCategory: CategorySummary[] = (() => {
    const map = new Map<string, CategorySummary>();

    for (const item of items) {
      const cat = (item.category || "Uncategorized").trim() || "Uncategorized";
      if (!map.has(cat)) {
        map.set(cat, { category: cat, count: 0, totalValue: 0 });
      }
      const entry = map.get(cat)!;
      entry.count += 1;
      if (typeof item.value === "number") {
        entry.totalValue += item.value;
      }
    }

    return Array.from(map.values()).sort(
      (a, b) => b.totalValue - a.totalValue
    );
  })();

  const categoryCount = byCategory.length;

  const headerStatus =
    state === "loading"
      ? "Loading from Supabase…"
      : state === "error"
      ? "Supabase error – showing debug info"
      : totalItems > 0
      ? "Live data from your items table"
      : "No items found yet – try adding some via Manual entry";

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
              Supabase analytics (beta)
            </Text>
            <Text style={[styles.headerSub, { color: colors.muted }]}>
              This screen reads directly from your Supabase items table, so it
              closes the loop from Manual entry → database → analytics.
            </Text>
          </View>
          <View style={styles.headerIcon}>
            <Ionicons name="server-outline" size={20} color={colors.accent} />
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
                    : state === "loading"
                    ? "#F59E0B"
                    : "#19A7AE"
                }
              />
            )}
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[styles.bannerTitle, { color: colors.text }]}>
              {headerStatus}
            </Text>
            {errorText ? (
              <Text style={[styles.bannerBody, { color: colors.muted }]}>
                {errorText}
              </Text>
            ) : (
              <Text style={[styles.bannerBody, { color: colors.muted }]}>
                If you see zeroes, try adding items via Manual entry first.
              </Text>
            )}
          </View>
        </View>

        {/* High-level metrics */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.metricsRow}>
            <View style={styles.metricBlock}>
              <Text style={[styles.metricLabel, { color: colors.muted }]}>
                Items in Supabase
              </Text>
              <Text style={[styles.metricValue, { color: colors.text }]}>
                {totalItems}
              </Text>
            </View>
            <View style={styles.metricBlock}>
              <Text style={[styles.metricLabel, { color: colors.muted }]}>
                Total value (approx.)
              </Text>
              <Text style={[styles.metricValue, { color: colors.text }]}>
                {formatCurrency(totalValue)}
              </Text>
            </View>
          </View>

          <View style={styles.metricsRow}>
            <View style={styles.metricBlock}>
              <Text style={[styles.metricLabel, { color: colors.muted }]}>
                Categories
              </Text>
              <Text style={[styles.metricValue, { color: colors.text }]}>
                {categoryCount}
              </Text>
            </View>
            <View style={styles.metricBlock}>
              <Text style={[styles.metricLabel, { color: colors.muted }]}>
                Source
              </Text>
              <Text style={[styles.metricValueSmall, { color: colors.muted }]}>
                items table (Supabase)
              </Text>
            </View>
          </View>
        </View>

        {/* Category breakdown */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.cardHeaderRow}>
            <Text style={[styles.cardTitle, { color: colors.text }]}>
              Top categories
            </Text>
            <Text style={[styles.cardHint, { color: colors.muted }]}>
              Sorted by total value
            </Text>
          </View>

          {byCategory.length === 0 ? (
            <Text style={[styles.emptyText, { color: colors.muted }]}>
              No categories yet – once you add items with categories, they will
              show up here.
            </Text>
          ) : (
            byCategory.map((entry, idx) => (
              <View key={entry.category}>
                <View style={styles.categoryRow}>
                  <View style={{ flex: 1 }}>
                    <Text
                      style={[styles.categoryName, { color: colors.text }]}
                    >
                      {entry.category}
                    </Text>
                    <Text
                      style={[styles.categoryMeta, { color: colors.muted }]}
                    >
                      {entry.count} items · {formatCurrency(entry.totalValue)}
                    </Text>
                  </View>
                  <View style={styles.categoryTagBox}>
                    <Text
                      style={[
                        styles.categoryTagText,
                        {
                          color:
                            idx === 0
                              ? "#0BA86C"
                              : idx === 1
                              ? "#19A7AE"
                              : "#647589",
                        },
                      ]}
                    >
                      Rank #{idx + 1}
                    </Text>
                  </View>
                </View>
                {idx < byCategory.length - 1 && (
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

        {/* Explanation card */}
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
          <Text style={[styles.cardTitle, { color: colors.text }]}>
            What this proves
          </Text>
          <Text style={[styles.explainer, { color: colors.muted }]}>
            • Items you add via Manual entry now land in Supabase.{"\n"}
            • This screen reads that same table and aggregates totals.{"\n"}
            • From here, you can expand into full P/L, risk bands, and category
              allocation charts without changing how items are stored.
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
    maxWidth: 260,
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
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 16,
  },
  metricsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 6,
  },
  metricBlock: {
    flex: 1,
    marginRight: 8,
  },
  metricLabel: {
    fontSize: 12,
  },
  metricValue: {
    fontSize: 18,
    fontWeight: "700",
    marginTop: 2,
  },
  metricValueSmall: {
    fontSize: 13,
    marginTop: 4,
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
  emptyText: {
    fontSize: 12,
  },
  categoryRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 6,
  },
  categoryName: {
    fontSize: 14,
    fontWeight: "600",
  },
  categoryMeta: {
    fontSize: 12,
    marginTop: 2,
  },
  categoryTagBox: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 999,
    backgroundColor: "#F3F6F8",
    marginLeft: 8,
  },
  categoryTagText: {
    fontSize: 11,
    fontWeight: "600",
  },
  separator: {
    height: StyleSheet.hairlineWidth,
    marginVertical: 6,
  },
  explainer: {
    fontSize: 12,
    lineHeight: 18,
  },
});

export default AnalyticsSupabaseDemo;
