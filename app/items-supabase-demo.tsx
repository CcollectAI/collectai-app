import React, { useEffect, useMemo, useState } from "react";
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { supabase } from "@/lib/supabase";
import { useAppTheme } from "@/hooks/useAppTheme";
type ItemRow = {
  id: string;
  title: string | null;
  category: string | null;
  value: number | null;
  source?: string | null;
};

// Compatibility: replace old ./ui/theme usage with app theme hook
const useAppColors = () => {
  const { colors } = useAppTheme();
  return colors;
};

type LoadState = "idle" | "loading" | "loaded" | "error";

const formatCurrency = (value: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
  }).format(value);

const ItemsSupabaseDemo: React.FC = () => {
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
          .select("id,title,category,value,source")
          .order("created_at", { ascending: false })
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

  const bySource = useMemo(() => {
    const map = new Map<string, number>();
    for (const item of items) {
      const src = (item.source || "unknown").toLowerCase();
      map.set(src, (map.get(src) ?? 0) + 1);
    }
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [items]);

  const headerStatus =
    state === "loading"
      ? "Loading items from Supabase…"
      : state === "error"
      ? "Supabase error – see details below"
      : totalItems > 0
      ? "Showing items from your Supabase items table"
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
              Items
            </Text>
            <Text style={[styles.headerTitle, { color: colors.text }]}>
              Supabase items (beta)
            </Text>
            <Text style={[styles.headerSub, { color: colors.muted }]}>
              This view reads directly from your Supabase items table. It&apos;s
              a bridge between Manual entry and your future full Items screen.
            </Text>
          </View>
          <View style={styles.headerIcon}>
            <Ionicons name="cube-outline" size={20} color={colors.accent} />
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
                If you see zero items, add some via Manual entry first.
              </Text>
            )}
          </View>
        </View>

        {/* Summary card */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.metricsRow}>
            <View style={styles.metricBlock}>
              <Text style={[styles.metricLabel, { color: colors.muted }]}>
                Items
              </Text>
              <Text style={[styles.metricValue, { color: colors.text }]}>
                {totalItems}
              </Text>
            </View>
            <View style={styles.metricBlock}>
              <Text style={[styles.metricLabel, { color: colors.muted }]}>
                Approx. value
              </Text>
              <Text style={[styles.metricValue, { color: colors.text }]}>
                {formatCurrency(totalValue)}
              </Text>
            </View>
          </View>

          <View style={styles.metricsRow}>
            <View style={styles.metricBlock}>
              <Text style={[styles.metricLabel, { color: colors.muted }]}>
                Distinct sources
              </Text>
              <Text style={[styles.metricValueSmall, { color: colors.text }]}>
                {bySource.length}
              </Text>
            </View>
            <View style={styles.metricBlock}>
              <Text style={[styles.metricLabel, { color: colors.muted }]}>
                Top source
              </Text>
              <Text style={[styles.metricValueSmall, { color: colors.muted }]}>
                {bySource[0]?.[0] ?? "—"}
              </Text>
            </View>
          </View>
        </View>

        {/* Items list */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.cardHeaderRow}>
            <Text style={[styles.cardTitle, { color: colors.text }]}>
              Items from Supabase
            </Text>
            <Text style={[styles.cardHint, { color: colors.muted }]}>
              Latest first
            </Text>
          </View>

          {items.length === 0 ? (
            <Text style={[styles.emptyText, { color: colors.muted }]}>
              No items in the table yet. Once you add items, they&apos;ll
              appear here.
            </Text>
          ) : (
            items.map((item, idx) => {
              const value =
                typeof item.value === "number" ? item.value : undefined;
              const cat = item.category || "Uncategorized";
              const title = item.title || "(Untitled item)";
              const src = item.source || "manual / unknown";

              return (
                <View key={item.id}>
                  <View style={styles.itemRow}>
                    <View style={styles.itemMain}>
                      <Text
                        style={[styles.itemTitle, { color: colors.text }]}
                        numberOfLines={1}
                      >
                        {title}
                      </Text>
                      <Text
                        style={[styles.itemMeta, { color: colors.muted }]}
                        numberOfLines={1}
                      >
                        {cat} · {src}
                      </Text>
                    </View>
                    <View style={styles.itemRight}>
                      <Text
                        style={[
                          styles.itemValue,
                          { color: colors.text },
                        ]}
                      >
                        {value !== undefined
                          ? formatCurrency(value)
                          : "—"}
                      </Text>
                    </View>
                  </View>
                  {idx < items.length - 1 && (
                    <View
                      style={[
                        styles.separator,
                        { backgroundColor: colors.border },
                      ]}
                    />
                  )}
                </View>
              );
            })
          )}
        </View>

        {/* Explainer card */}
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
            Next steps from here
          </Text>
          <Text style={[styles.explainer, { color: colors.muted }]}>
            • Merge this Supabase-backed list into your main Items tab once
              you&apos;re happy with it.{"\n"}
            • Extend the row to show trends, tiers, or fraud checks per item.{"\n"}
            • Use the same data source in Analytics and Events/Drops for a
              consistent portfolio view.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 16, paddingVertical: 12 },
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
  headerTitle: { fontSize: 22, fontWeight: "700", marginTop: 2 },
  headerSub: { fontSize: 12, marginTop: 4, maxWidth: 260 },
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
  bannerTitle: { fontSize: 13, fontWeight: "600" },
  bannerBody: { fontSize: 11, marginTop: 2 },
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
  metricBlock: { flex: 1, marginRight: 8 },
  metricLabel: { fontSize: 12 },
  metricValue: { fontSize: 18, fontWeight: "700", marginTop: 2 },
  metricValueSmall: { fontSize: 13, marginTop: 4 },
  cardHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  cardTitle: { fontSize: 16, fontWeight: "600" },
  cardHint: { fontSize: 11 },
  emptyText: { fontSize: 12 },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 6,
  },
  itemMain: { flex: 1, paddingRight: 8 },
  itemTitle: { fontSize: 14, fontWeight: "600" },
  itemMeta: { fontSize: 12, marginTop: 2 },
  itemRight: { alignItems: "flex-end" },
  itemValue: { fontSize: 14, fontWeight: "600" },
  separator: { height: StyleSheet.hairlineWidth, marginVertical: 6 },
  explainer: { fontSize: 12, lineHeight: 18 },
});

export default ItemsSupabaseDemo;
