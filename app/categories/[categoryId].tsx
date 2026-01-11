import React, { useMemo } from "react";
import { View, Text, ScrollView, Pressable, StyleSheet } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";

import { getCategoryById } from "@/data/categories";

type Category = {
  id: string;
  name: string;
  description?: string;
  heroLine?: string;
};

type CollectionCard = {
  id: string;
  title: string;
  subtitle?: string;
  chips?: string[];
  // later: image, floor price, volatility, etc
};

const DARK = {
  BG: "#0f172a",
  CARD: "#020617",
  BORDER: "#1f2933",
  TEXT: "#e5e7eb",
  MUTED: "#9ca3af",
  PRIMARY: "#0ea5e9",
  CHIP: "rgba(14,165,233,0.14)",
};

function safeDecode(x?: string | string[]) {
  const raw = Array.isArray(x) ? x[0] : x;
  return raw ? decodeURIComponent(String(raw)) : "";
}

function buildFallbackCollections(categoryId: string): CollectionCard[] {
  // Safe “Amazon brandstore” collections even if you haven’t wired real data yet
  // You can replace this later with real config/data.
  const common: CollectionCard[] = [
    { id: `${categoryId}-grails`, title: "Grails & high value", subtitle: "Blue-chip, premium, iconic", chips: ["Blue chip", "Long-term"] },
    { id: `${categoryId}-new`, title: "New & trending", subtitle: "Fresh drops + rising demand", chips: ["Trending", "Volatile"] },
    { id: `${categoryId}-sealed`, title: "Sealed / boxed", subtitle: "Condition-first collecting", chips: ["Condition", "Scarcity"] },
    { id: `${categoryId}-budget`, title: "Budget finds", subtitle: "Underrated value", chips: ["Value", "Hidden gems"] },
  ];

  // Light category-specific flavor (optional)
  if (categoryId.toLowerCase().includes("pokemon")) {
    return [
      { id: "pokemon-vintage", title: "Vintage WOTC era", subtitle: "Base / Jungle / Fossil", chips: ["Vintage", "Iconic"] },
      { id: "pokemon-altarts", title: "Modern alt arts", subtitle: "High demand singles", chips: ["Modern", "Liquid"] },
      { id: "pokemon-graded", title: "Graded slabs", subtitle: "PSA/BGS/CGC focus", chips: ["Condition", "Premium"] },
      ...common,
    ].slice(0, 6);
  }
  if (categoryId.toLowerCase().includes("gunpla")) {
    return [
      { id: "gunpla-mg", title: "Master Grade (MG)", subtitle: "Build depth + display value", chips: ["Builders", "Display"] },
      { id: "gunpla-pg", title: "Perfect Grade (PG)", subtitle: "Premium builds", chips: ["Premium", "Rare"] },
      { id: "gunpla-limited", title: "Limited / P-Bandai", subtitle: "Scarcity-driven", chips: ["Scarce", "Collectors"] },
      ...common,
    ].slice(0, 6);
  }
  if (categoryId.toLowerCase().includes("warhammer")) {
    return [
      { id: "wh-aos", title: "Age of Sigmar", subtitle: "Armies + meta shifts", chips: ["Meta", "Community"] },
      { id: "wh-40k", title: "Warhammer 40K", subtitle: "High volume market", chips: ["Liquid", "Active"] },
      { id: "wh-oop", title: "OOP minis", subtitle: "Retired kits", chips: ["OOP", "Scarce"] },
      ...common,
    ].slice(0, 6);
  }

  return common;
}

const Chip: React.FC<{ text: string; tone?: "muted" | "primary" }> = ({ text, tone = "muted" }) => {
  return (
    <View
      style={[
        styles.chip,
        {
          backgroundColor: tone === "primary" ? DARK.CHIP : DARK.CARD,
          borderColor: DARK.BORDER,
        },
      ]}
    >
      <Text style={[styles.chipText, { color: tone === "primary" ? DARK.TEXT : DARK.MUTED }]} numberOfLines={1}>
        {text}
      </Text>
    </View>
  );
};

export default function CategoryOverviewBrandstore() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const { categoryId } = useLocalSearchParams<{ categoryId?: string | string[] }>();
  const categoryIdStr = safeDecode(categoryId);

  const category = useMemo(() => {
    if (!categoryIdStr) return undefined;
    return getCategoryById(categoryIdStr as any) as Category | undefined;
  }, [categoryIdStr]);

  const title = category?.name ?? (categoryIdStr ? categoryIdStr.toUpperCase() : "Category");
  const heroLine =
    (category as any)?.heroLine ||
    "A focused storefront for collectors — curated collections, community signals, and high-signal context.";

  const description =
    category?.description ||
    "Explore curated sub-collections inside this category. Use it like an Amazon Brandstore: browse, compare, then jump into community or items.";

  const collections = useMemo(() => buildFallbackCollections(categoryIdStr || "category"), [categoryIdStr]);

  const openChat = () => {
    if (!categoryIdStr) return;
    router.push({ pathname: "/chat/category/[categoryId]", params: { categoryId: categoryIdStr } } as any);
  };

  const openCollection = (c: CollectionCard) => {
    // For now: route to category chat with a “collection” hint.
    // Later, this can route to: /collections/[id] or filtered /items?categoryId=...
    if (!categoryIdStr) return;
    router.push({
      pathname: "/chat/category/[categoryId]" as any,
      params: { categoryId: categoryIdStr, collection: c.id },
    } as any);
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: DARK.BG }]} edges={["top", "left", "right"]}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={[
          styles.container,
          { paddingTop: Math.max(12, insets.top), paddingBottom: 28 },
        ]}
      >
        {/* Header */}
        <View style={styles.headerRow}>
          <Pressable onPress={() => router.back()} style={[styles.iconBtn, { borderColor: DARK.BORDER }]}>
            <Ionicons name="chevron-back" size={18} color={DARK.MUTED} />
          </Pressable>

          <View style={{ flex: 1, paddingHorizontal: 10 }}>
            <Text style={[styles.headerTitle, { color: DARK.TEXT }]} numberOfLines={1}>
              {title}
            </Text>
            <Text style={[styles.headerSub, { color: DARK.MUTED }]} numberOfLines={1}>
              Category storefront
            </Text>
          </View>

          <Pressable onPress={openChat} style={[styles.iconBtn, { borderColor: DARK.BORDER }]}>
            <Ionicons name="chatbubble-ellipses-outline" size={18} color={DARK.MUTED} />
          </Pressable>
        </View>

        {/* Hero (Amazon brandstore vibe) */}
        <View style={[styles.card, { backgroundColor: DARK.CARD, borderColor: DARK.BORDER }]}>
          <Text style={[styles.heroLine, { color: DARK.TEXT }]}>{heroLine}</Text>
          <Text style={[styles.body, { color: DARK.MUTED }]}>{description}</Text>

          <View style={styles.chipRow}>
            <Chip text="Curated collections" tone="primary" />
            <Chip text="Community signals" />
            <Chip text="Portfolio-aware (soon)" />
          </View>

          <View style={styles.ctaRow}>
            <Pressable onPress={openChat} style={[styles.primaryBtn, { backgroundColor: DARK.PRIMARY, borderColor: DARK.BORDER }]}>
              <Ionicons name="people-outline" size={16} color="#fff" style={{ marginRight: 6 }} />
              <Text style={styles.primaryText}>Open community</Text>
            </Pressable>

            <Pressable onPress={() => {}} style={[styles.secondaryBtn, { backgroundColor: DARK.CARD, borderColor: DARK.BORDER }]}>
              <Ionicons name="funnel-outline" size={16} color={DARK.MUTED} style={{ marginRight: 6 }} />
              <Text style={[styles.secondaryText, { color: DARK.MUTED }]}>Filter items</Text>
            </Pressable>
          </View>
        </View>

        {/* Collections carousel */}
        <View style={[styles.card, { backgroundColor: DARK.CARD, borderColor: DARK.BORDER }]}>
          <View style={styles.sectionHead}>
            <Text style={[styles.sectionTitle, { color: DARK.TEXT }]}>Collections in {title}</Text>
            <Text style={[styles.sectionHint, { color: DARK.MUTED }]}>Swipe to browse curated sets</Text>
          </View>

          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingTop: 10, paddingBottom: 2 }}>
            {collections.map((c) => (
              <Pressable
                key={c.id}
                onPress={() => openCollection(c)}
                style={[styles.carouselCard, { backgroundColor: DARK.BG, borderColor: DARK.BORDER }]}
              >
                <View style={styles.carouselTop}>
                  <View style={[styles.iconBubble, { backgroundColor: DARK.PRIMARY }]}>
                    <Ionicons name="cube-outline" size={18} color="#fff" />
                  </View>
                  <Ionicons name="chevron-forward" size={16} color={DARK.MUTED} />
                </View>

                <Text style={[styles.carouselTitle, { color: DARK.TEXT }]} numberOfLines={2}>
                  {c.title}
                </Text>
                {!!c.subtitle && (
                  <Text style={[styles.carouselSub, { color: DARK.MUTED }]} numberOfLines={2}>
                    {c.subtitle}
                  </Text>
                )}

                <View style={styles.carouselChips}>
                  {(c.chips ?? []).slice(0, 3).map((t) => (
                    <View key={t} style={[styles.tinyChip, { borderColor: DARK.BORDER }]}>
                      <Text style={[styles.tinyChipText, { color: DARK.MUTED }]} numberOfLines={1}>
                        {t}
                      </Text>
                    </View>
                  ))}
                </View>
              </Pressable>
            ))}
          </ScrollView>
        </View>

        {/* Footer section */}
        <View style={[styles.card, { backgroundColor: DARK.CARD, borderColor: DARK.BORDER }]}>
          <Text style={[styles.sectionTitle, { color: DARK.TEXT }]}>What to watch</Text>
          <Text style={[styles.body, { color: DARK.MUTED }]}>
            Add watchlist rules, floor-price alerts, and “drop radar” here later (connects to analytics + marketplace comps).
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  container: { paddingHorizontal: 16 },

  headerRow: { flexDirection: "row", alignItems: "center", marginBottom: 12 },
  iconBtn: {
    width: 36,
    height: 36,
    borderRadius: 999,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: { fontSize: 16, fontWeight: "900" },
  headerSub: { marginTop: 2, fontSize: 11, fontWeight: "600" },

  card: { borderRadius: 16, borderWidth: 1, padding: 12, marginBottom: 10 },

  heroLine: { fontSize: 14, fontWeight: "900" },
  body: { marginTop: 10, fontSize: 12, lineHeight: 17, fontWeight: "600" },

  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 12 },
  chip: { paddingVertical: 6, paddingHorizontal: 10, borderRadius: 999, borderWidth: 1 },
  chipText: { fontSize: 11, fontWeight: "800" },

  ctaRow: { marginTop: 12, flexDirection: "row", alignItems: "center", gap: 8 },
  primaryBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
  },
  primaryText: { color: "#fff", fontSize: 12, fontWeight: "900" },

  secondaryBtn: {
    paddingVertical: 10,
    paddingHorizontal: 10,
    borderRadius: 12,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
  },
  secondaryText: { fontSize: 12, fontWeight: "800" },

  sectionHead: {},
  sectionTitle: { fontSize: 13, fontWeight: "900" },
  sectionHint: { marginTop: 6, fontSize: 11, fontWeight: "600" },

  carouselCard: {
    width: 220,
    borderRadius: 16,
    borderWidth: 1,
    padding: 12,
    marginRight: 10,
  },
  carouselTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  iconBubble: { width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center" },
  carouselTitle: { marginTop: 10, fontSize: 13, fontWeight: "900" },
  carouselSub: { marginTop: 6, fontSize: 11, fontWeight: "600" },

  carouselChips: { marginTop: 10, flexDirection: "row", flexWrap: "wrap", gap: 6 },
  tinyChip: { borderWidth: 1, borderRadius: 999, paddingVertical: 4, paddingHorizontal: 8 },
  tinyChipText: { fontSize: 10, fontWeight: "800" },
});
