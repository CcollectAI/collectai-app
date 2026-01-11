import React, { useMemo, useState } from "react";
import { View, Text, ScrollView, Pressable, StyleSheet, Dimensions } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";

import { getCategoryById } from "@/data/categories";

type Highlight = {
  id: string;
  title: string;
  subtitle: string;
  badge?: string;
  bullets: string[];
  stats: Array<{ label: string; value: string }>;
};

type BrandKpis = {
  collections: number;
  segments: Array<{ label: string; value: string }>;
  totals: Array<{ label: string; value: string }>;
  signals: Array<{ label: string; value: string }>;
};

const DARK = {
  BG: "#0f172a",
  CARD: "#020617",
  BORDER: "#1f2933",
  TEXT: "#e5e7eb",
  MUTED: "#9ca3af",
  NAVY: "#0C2233",
  ACCENT: "#38d6c7",
};

const LIGHT = {
  BG: "#f4f4f5",
  CARD: "#ffffff",
  BORDER: "#e5e7eb",
  TEXT: "#0f172a",
  MUTED: "#6b7280",
  NAVY: "#0C2233",
  ACCENT: "#38d6c7",
};

function titleCase(s: string) {
  return String(s ?? "")
    .replace(/[_-]+/g, " ")
    .trim()
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

/**
 * Brand-store content model (generalized, "wiki"/brand POV).
 * Replace these mock numbers later with real backend aggregation.
 */
function getBrandStoreModel(categoryId: string | undefined | null): {
  kpis: BrandKpis;
  highlights: Highlight[];
  copy: { about: string; whatToCollect: string[]; howToSpotValue: string[] };
} {
  const id = String(categoryId ?? "").toLowerCase();

  // Base fallback
  const base = {
    kpis: {
      collections: 6,
      totals: [
        { label: "SKUs / items", value: "120+" },
        { label: "Active collectors", value: "1.2k" },
        { label: "Avg. liquidity", value: "Medium" },
      ],
      segments: [
        { label: "Mainline", value: "60%" },
        { label: "Limited", value: "25%" },
        { label: "Promos", value: "15%" },
      ],
      signals: [
        { label: "Volatility", value: "Moderate" },
        { label: "Counterfeit risk", value: "Medium" },
        { label: "Data coverage", value: "Good" },
      ],
    },
    highlights: [
      {
        id: "starter",
        title: "Starter Essentials",
        subtitle: "High-signal entry points collectors actually track.",
        badge: "Beginner-friendly",
        bullets: ["Liquid, easy comps", "Lower counterfeit exposure", "Clear condition standards"],
        stats: [
          { label: "Liquidity", value: "High" },
          { label: "Volatility", value: "Low" },
          { label: "Comps", value: "Strong" },
        ],
      },
      {
        id: "premium",
        title: "Premium Picks",
        subtitle: "Scarcity + narrative drive long-term upside.",
        badge: "Higher variance",
        bullets: ["Story-driven demand", "Seasonal spikes", "Supply shocks matter"],
        stats: [
          { label: "Liquidity", value: "Medium" },
          { label: "Volatility", value: "High" },
          { label: "Comps", value: "Mixed" },
        ],
      },
    ],
    copy: {
      about:
        "A brand-style overview of the category: what exists, how collectors segment it, and which signals typically matter for value discovery. This page is designed like an Amazon Brand Store — generalized, not personal to any one collector.",
      whatToCollect: [
        "Mainline releases (high coverage)",
        "Limited/numbered runs (scarcity)",
        "Crossovers/collabs (narrative-driven)",
      ],
      howToSpotValue: [
        "Look for low supply + persistent demand",
        "Track comps + condition standards",
        "Beware counterfeit-heavy subsegments",
      ],
    },
  };

  if (id === "pokemon") {
    return {
      kpis: {
        collections: 14,
        totals: [
          { label: "Sets", value: "200+" },
          { label: "Cards", value: "25k+" },
          { label: "Grading demand", value: "Very high" },
        ],
        segments: [
          { label: "Modern", value: "55%" },
          { label: "Vintage", value: "25%" },
          { label: "Promos", value: "20%" },
        ],
        signals: [
          { label: "Volatility", value: "High" },
          { label: "Counterfeit risk", value: "High" },
          { label: "Data coverage", value: "Excellent" },
        ],
      },
      highlights: [
        {
          id: "sv-era",
          title: "Scarlet & Violet Era",
          subtitle: "High volume, strong liquidity, clear comp lines.",
          badge: "Mainline",
          bullets: ["Chase cards drive liquidity", "Rapid set cadence", "Condition variance matters"],
          stats: [
            { label: "Liquidity", value: "High" },
            { label: "Volatility", value: "Medium" },
            { label: "Comps", value: "Excellent" },
          ],
        },
        {
          id: "vintage",
          title: "WOTC & Early Vintage",
          subtitle: "Narrative + scarcity; grading is the language.",
          badge: "Blue-chip",
          bullets: ["Population reports matter", "Low supply in high grades", "Longer hold horizons"],
          stats: [
            { label: "Liquidity", value: "Medium" },
            { label: "Volatility", value: "High" },
            { label: "Comps", value: "Strong" },
          ],
        },
        {
          id: "promos",
          title: "Promos & Special Prints",
          subtitle: "Event-driven spikes + thin markets.",
          badge: "Spike-prone",
          bullets: ["Thin markets", "Story-driven demand", "Authenticity checks"],
          stats: [
            { label: "Liquidity", value: "Low–Med" },
            { label: "Volatility", value: "High" },
            { label: "Comps", value: "Mixed" },
          ],
        },
      ],
      copy: {
        about:
          "Pokémon is a global collectibles ecosystem spanning sets, promos, sealed, and graded singles. The market is deep but volatile; the highest signal comes from condition, print variants, and repeatable comps.",
        whatToCollect: ["Mainline sets (sealed + singles)", "Vintage graded staples", "Event promos with provenance"],
        howToSpotValue: ["Population + sales velocity", "Condition sensitivity (centering/edges)", "Beware reprints + counterfeit channels"],
      },
    };
  }

  if (id === "warhammer") {
    return {
      kpis: {
        collections: 9,
        totals: [
          { label: "Factions", value: "25+" },
          { label: "Model lines", value: "300+" },
          { label: "Paint premium", value: "High impact" },
        ],
        segments: [
          { label: "Meta staples", value: "40%" },
          { label: "Limited/OOP", value: "30%" },
          { label: "Showcase builds", value: "30%" },
        ],
        signals: [
          { label: "Volatility", value: "Medium" },
          { label: "Counterfeit risk", value: "Low–Med" },
          { label: "Data coverage", value: "Moderate" },
        ],
      },
      highlights: [
        {
          id: "oop",
          title: "Out-of-Print & Limited Runs",
          subtitle: "Scarcity-driven pricing; supply shocks are real.",
          badge: "OOP",
          bullets: ["Retirement announcements move markets", "Completeness matters", "Packaging can add premium"],
          stats: [
            { label: "Liquidity", value: "Medium" },
            { label: "Volatility", value: "Med–High" },
            { label: "Comps", value: "Moderate" },
          ],
        },
        {
          id: "display",
          title: "Display / Showcase Builds",
          subtitle: "Paint quality becomes the primary value driver.",
          badge: "Craft premium",
          bullets: ["Provenance + artist reputation", "Photo quality matters", "Commission norms apply"],
          stats: [
            { label: "Liquidity", value: "Low–Med" },
            { label: "Volatility", value: "Medium" },
            { label: "Comps", value: "Mixed" },
          ],
        },
      ],
      copy: {
        about:
          "Warhammer minis combine hobby craft and collectibility. Value is shaped by retirement cycles, faction demand, and build/paint quality — often more than raw MSRP.",
        whatToCollect: ["OOP kits with provenance", "Faction staples", "High-quality display builds"],
        howToSpotValue: ["Retirement + availability", "Paint/assembly execution", "Faction demand cycles"],
      },
    };
  }

  if (id === "lego") {
    return {
      kpis: {
        collections: 10,
        totals: [
          { label: "Themes", value: "20+" },
          { label: "Retired sets", value: "Thousands" },
          { label: "Sealed premium", value: "Strong" },
        ],
        segments: [
          { label: "Retired", value: "50%" },
          { label: "Icons/Display", value: "30%" },
          { label: "Minifigs", value: "20%" },
        ],
        signals: [
          { label: "Volatility", value: "Low–Med" },
          { label: "Counterfeit risk", value: "Low" },
          { label: "Data coverage", value: "Good" },
        ],
      },
      highlights: [
        {
          id: "retired",
          title: "Retired Icons",
          subtitle: "Stable holds; sealed condition carries premium.",
          badge: "Retired",
          bullets: ["Retirement is the catalyst", "Box condition matters", "Part-out floor exists"],
          stats: [
            { label: "Liquidity", value: "High" },
            { label: "Volatility", value: "Low–Med" },
            { label: "Comps", value: "Good" },
          ],
        },
        {
          id: "minifigs",
          title: "Minifig Economy",
          subtitle: "Small-ticket liquidity with frequent price discovery.",
          badge: "Liquid",
          bullets: ["Completeness matters", "Variant detection", "High turnover"],
          stats: [
            { label: "Liquidity", value: "High" },
            { label: "Volatility", value: "Medium" },
            { label: "Comps", value: "Good" },
          ],
        },
      ],
      copy: {
        about:
          "LEGO value is shaped by retirement cycles and sealed condition premiums. Subsegments like minifigs and rare parts create liquid micro-markets.",
        whatToCollect: ["Retired sealed sets", "High-demand themes", "Rare minifigs/variants"],
        howToSpotValue: ["Retirement + low inventory", "Seal integrity", "Theme demand durability"],
      },
    };
  }

  // ---- Expanded category brand-store models ----

  // Gunpla & model kits
  if (id === "gunpla" || id === "model-kits" || id === "model_kits") {
    return {
      kpis: {
        collections: 11,
        totals: [
          { label: "Lines", value: "HG / RG / MG / PG" },
          { label: "Variants", value: "Limited + P-Bandai" },
          { label: "Build premium", value: "Very high" },
        ],
        segments: [
          { label: "Mainline retail", value: "55%" },
          { label: "P-Bandai / limited", value: "30%" },
          { label: "Custom builds", value: "15%" },
        ],
        signals: [
          { label: "Volatility", value: "Medium" },
          { label: "Counterfeit risk", value: "Low–Med" },
          { label: "Data coverage", value: "Moderate" },
        ],
      },
      highlights: [
        {
          id: "rg-core",
          title: "Real Grade Core Line",
          subtitle: "High display value with strong liquidity and clear comps.",
          badge: "Core",
          bullets: ["Popular SKUs = repeatable comps", "Box condition matters", "Incomplete kits discount hard"],
          stats: [
            { label: "Liquidity", value: "High" },
            { label: "Volatility", value: "Med" },
            { label: "Comps", value: "Good" },
          ],
        },
        {
          id: "pbandai",
          title: "P-Bandai / Limited Drops",
          subtitle: "Supply shocks, short windows, and collector narratives.",
          badge: "Limited",
          bullets: ["Drop timing matters", "Thin comps early", "Sealed premium can be strong"],
          stats: [
            { label: "Liquidity", value: "Med" },
            { label: "Volatility", value: "High" },
            { label: "Comps", value: "Mixed" },
          ],
        },
        {
          id: "custom",
          title: "Custom / Painted Builds",
          subtitle: "Craft premium dominates price discovery.",
          badge: "Craft",
          bullets: ["Artist reputation matters", "Photo quality matters", "Build quality verification is key"],
          stats: [
            { label: "Liquidity", value: "Low–Med" },
            { label: "Volatility", value: "Med" },
            { label: "Comps", value: "Mixed" },
          ],
        },
      ],
      copy: {
        about:
          "Gunpla blends retail collectibility with hobby craft. Value is shaped by scarcity (especially limited runs), completeness, and build/paint execution for showcase pieces.",
        whatToCollect: ["Core line best-sellers", "P-Bandai limited variants", "High-quality custom builds (provenance)"],
        howToSpotValue: ["Completeness + seal integrity", "Limited run scarcity + demand persistence", "Build quality (gates, decals, finish)"],
      },
    };
  }

  // Magic: The Gathering
  if (id === "mtg" || id === "magic" || id === "magic-the-gathering" || id === "magic_the_gathering") {
    return {
      kpis: {
        collections: 16,
        totals: [
          { label: "Formats", value: "EDH / Modern / Legacy" },
          { label: "Liquidity", value: "Very high" },
          { label: "Reprint risk", value: "High" },
        ],
        segments: [
          { label: "Staples", value: "50%" },
          { label: "Collectors/variants", value: "30%" },
          { label: "Reserved List", value: "20%" },
        ],
        signals: [
          { label: "Volatility", value: "High" },
          { label: "Counterfeit risk", value: "Medium" },
          { label: "Data coverage", value: "Excellent" },
        ],
      },
      highlights: [
        {
          id: "edh-staples",
          title: "Commander Staples",
          subtitle: "Demand durability across metas; best comp coverage.",
          badge: "Staples",
          bullets: ["Broad demand base", "Reprints compress peaks", "Condition + authenticity checks"],
          stats: [
            { label: "Liquidity", value: "High" },
            { label: "Volatility", value: "Med–High" },
            { label: "Comps", value: "Excellent" },
          ],
        },
        {
          id: "reserved",
          title: "Reserved List",
          subtitle: "Structural scarcity; long horizon holds.",
          badge: "Scarce",
          bullets: ["Narrative scarcity", "Sensitive to macro cycles", "Authentication is critical"],
          stats: [
            { label: "Liquidity", value: "Medium" },
            { label: "Volatility", value: "High" },
            { label: "Comps", value: "Strong" },
          ],
        },
        {
          id: "collector-variants",
          title: "Collector Variants",
          subtitle: "Foils, serialized, special frames — story drives price.",
          badge: "Variants",
          bullets: ["Thin comps early", "Print run knowledge helps", "Condition sensitivity higher"],
          stats: [
            { label: "Liquidity", value: "Low–Med" },
            { label: "Volatility", value: "High" },
            { label: "Comps", value: "Mixed" },
          ],
        },
      ],
      copy: {
        about:
          "MTG is a highly liquid market with deep data coverage. The key risk is reprints; the key advantage is consistent demand from formats like Commander.",
        whatToCollect: ["Commander staples", "Reserved List anchors", "High-signal premium variants"],
        howToSpotValue: ["Reprint risk assessment", "Format demand durability", "Authenticity + condition checks"],
      },
    };
  }

  // Disney Lorcana
  if (id === "lorcana" || id === "disney-lorcana" || id === "disney_lorcana") {
    return {
      kpis: {
        collections: 8,
        totals: [
          { label: "Set cadence", value: "Fast" },
          { label: "Sealed premium", value: "Early-cycle" },
          { label: "Liquidity", value: "Growing" },
        ],
        segments: [
          { label: "Chase singles", value: "45%" },
          { label: "Sealed", value: "35%" },
          { label: "Promos", value: "20%" },
        ],
        signals: [
          { label: "Volatility", value: "High" },
          { label: "Counterfeit risk", value: "Medium" },
          { label: "Data coverage", value: "Good" },
        ],
      },
      highlights: [
        {
          id: "chase",
          title: "Chase Singles",
          subtitle: "High attention + fast price discovery when hype peaks.",
          badge: "Chase",
          bullets: ["Event spikes", "Condition sensitivity", "Liquidity is good at peak interest"],
          stats: [
            { label: "Liquidity", value: "High" },
            { label: "Volatility", value: "High" },
            { label: "Comps", value: "Good" },
          ],
        },
        {
          id: "sealed",
          title: "Sealed Product",
          subtitle: "Supply timing + reprints can compress returns.",
          badge: "Sealed",
          bullets: ["Track print waves", "Distribution matters", "Longer horizon holds"],
          stats: [
            { label: "Liquidity", value: "Medium" },
            { label: "Volatility", value: "High" },
            { label: "Comps", value: "Moderate" },
          ],
        },
      ],
      copy: {
        about:
          "Lorcana behaves like a modern TCG: hype cycles, fast set cadence, and price discovery driven by chase singles and sealed availability.",
        whatToCollect: ["Chase singles with durable demand", "Early-era sealed (carefully)", "Event promos with provenance"],
        howToSpotValue: ["Supply wave tracking", "Demand persistence after hype", "Authenticity checks"],
      },
    };
  }

  // Flesh and Blood
  if (id === "flesh-and-blood" || id === "flesh_and_blood" || id === "fab") {
    return {
      kpis: {
        collections: 9,
        totals: [
          { label: "Rarity focus", value: "Cold foils / fabled" },
          { label: "Liquidity", value: "Medium" },
          { label: "Community depth", value: "Strong" },
        ],
        segments: [
          { label: "Meta staples", value: "45%" },
          { label: "Premium foils", value: "35%" },
          { label: "Sealed", value: "20%" },
        ],
        signals: [
          { label: "Volatility", value: "Medium–High" },
          { label: "Counterfeit risk", value: "Low–Med" },
          { label: "Data coverage", value: "Moderate" },
        ],
      },
      highlights: [
        {
          id: "premium",
          title: "Premium Foils (Cold Foil)",
          subtitle: "Collector-focused segment; condition + provenance matter.",
          badge: "Premium",
          bullets: ["Thin comps", "High condition sensitivity", "Buyer trust signals matter"],
          stats: [
            { label: "Liquidity", value: "Low–Med" },
            { label: "Volatility", value: "High" },
            { label: "Comps", value: "Mixed" },
          ],
        },
        {
          id: "meta",
          title: "Playable Staples",
          subtitle: "Demand tied to hero metas and competitive seasonality.",
          badge: "Playable",
          bullets: ["Meta rotations", "Reprint effects", "Better liquidity than premiums"],
          stats: [
            { label: "Liquidity", value: "Medium" },
            { label: "Volatility", value: "Med–High" },
            { label: "Comps", value: "Good" },
          ],
        },
      ],
      copy: {
        about:
          "Flesh and Blood is driven by competitive play and collector-tier premium treatments. Value concentrates in premium foils and persistent meta staples.",
        whatToCollect: ["Cold foils with strong demand", "Staples used across metas", "Selective sealed (early-era)"],
        howToSpotValue: ["Hero meta + season timing", "Condition + authenticity", "Liquidity differences by subsegment"],
      },
    };
  }

  // Designer / Art Toys
  if (id === "designer-toys" || id === "designer_toys" || id === "art-toys" || id === "art_toys") {
    return {
      kpis: {
        collections: 10,
        totals: [
          { label: "Drops", value: "Frequent" },
          { label: "Liquidity", value: "Medium" },
          { label: "Narrative premium", value: "Very high" },
        ],
        segments: [
          { label: "Artist core lines", value: "50%" },
          { label: "Collabs", value: "30%" },
          { label: "Ultra-limited", value: "20%" },
        ],
        signals: [
          { label: "Volatility", value: "High" },
          { label: "Counterfeit risk", value: "Medium" },
          { label: "Data coverage", value: "Moderate" },
        ],
      },
      highlights: [
        {
          id: "core",
          title: "Artist Core Lines",
          subtitle: "Most consistent comps; community-known releases.",
          badge: "Core",
          bullets: ["Repeatable demand", "Better price discovery", "Packaging matters"],
          stats: [
            { label: "Liquidity", value: "Medium" },
            { label: "Volatility", value: "Medium" },
            { label: "Comps", value: "Good" },
          ],
        },
        {
          id: "collabs",
          title: "Collabs & Event Drops",
          subtitle: "Thin supply + story spikes; verify provenance.",
          badge: "Collab",
          bullets: ["Event-driven premiums", "Thin comps", "Counterfeit exposure"],
          stats: [
            { label: "Liquidity", value: "Low–Med" },
            { label: "Volatility", value: "High" },
            { label: "Comps", value: "Mixed" },
          ],
        },
      ],
      copy: {
        about:
          "Designer toys behave like culture-driven assets: artist reputation, collab narratives, and drop mechanics dominate value discovery. Provenance and authenticity signals matter.",
        whatToCollect: ["Artist core lines", "High-signal collabs", "Event drops with provenance"],
        howToSpotValue: ["Artist reputation + community demand", "Provenance verification", "Drop scarcity vs long-term demand"],
      },
    };
  }

  // ---- End expanded models ----

  return base;
}

const { width: SCREEN_W } = Dimensions.get("window");
const CARD_W = Math.min(320, Math.max(260, Math.floor(SCREEN_W * 0.78)));

const MetricChip: React.FC<{ label: string; value: string; theme: any }> = ({ label, value, theme }) => {
  return (
    <View style={[styles.metricChip, { borderColor: theme.BORDER, backgroundColor: theme.CARD }]}>
      <Text style={[styles.metricValue, { color: theme.TEXT }]}>{value}</Text>
      <Text style={[styles.metricLabel, { color: theme.MUTED }]}>{label}</Text>
    </View>
  );
};

const Section: React.FC<{ title: string; theme: any; children: React.ReactNode; right?: React.ReactNode }> = ({
  title,
  theme,
  children,
  right,
}) => {
  return (
    <View style={[styles.sectionCard, { backgroundColor: theme.CARD, borderColor: theme.BORDER }]}>
      <View style={styles.sectionHeader}>
        <Text style={[styles.sectionTitle, { color: theme.TEXT }]}>{title}</Text>
        <View style={{ flex: 1 }} />
        {right ?? null}
      </View>
      {children}
    </View>
  );
};

export default function CategoryOverviewScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { categoryId } = useLocalSearchParams<{ categoryId?: string }>();

  const [isDark, setIsDark] = useState(true);
  const theme = isDark ? DARK : LIGHT;

  const category = useMemo(() => (categoryId ? getCategoryById(categoryId as any) : undefined), [categoryId]);
  const model = useMemo(() => getBrandStoreModel(categoryId), [categoryId]);

  const name = category?.name ?? titleCase(String(categoryId ?? "Category"));

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: theme.BG }]} edges={["top", "left", "right"]}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{
          paddingTop: Math.max(10, insets.top + 6),
          paddingBottom: 24,
          paddingHorizontal: 16,
        }}
      >
        {/* Top bar */}
        <View style={styles.topBar}>
          <Pressable
            onPress={() => router.back()}
            style={[styles.iconBtn, { borderColor: theme.BORDER, backgroundColor: theme.CARD }]}
            accessibilityRole="button"
          >
            <Ionicons name="chevron-back" size={18} color={theme.MUTED} />
          </Pressable>

          <View style={{ flex: 1, paddingHorizontal: 10 }}>
            <Text style={[styles.topTitle, { color: theme.TEXT }]} numberOfLines={1}>
              {name}
            </Text>
            <Text style={[styles.topSub, { color: theme.MUTED }]} numberOfLines={1}>
              Category overview • brand / wiki perspective
            </Text>
          </View>

          <Pressable
            onPress={() => setIsDark((v) => !v)}
            style={[styles.iconBtn, { borderColor: theme.BORDER, backgroundColor: theme.CARD }]}
            accessibilityRole="button"
          >
            <Ionicons name={isDark ? "sunny-outline" : "moon-outline"} size={18} color={theme.MUTED} />
          </Pressable>
        </View>

        {/* Hero */}
        <View style={[styles.hero, { backgroundColor: theme.CARD, borderColor: theme.BORDER }]}>
          <View style={styles.heroRow}>
            <View style={[styles.heroMark, { backgroundColor: theme.ACCENT }]} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.heroTitle, { color: theme.TEXT }]} numberOfLines={2}>
                {name}
              </Text>
              <Text style={[styles.heroDesc, { color: theme.MUTED }]}>{model.copy.about}</Text>
            </View>
          </View>

          {/* KPIs */}
          <View style={styles.metricsRow}>
            <MetricChip theme={theme} label="Collections" value={String(model.kpis.collections)} />
            {model.kpis.totals.slice(0, 2).map((t) => (
              <MetricChip key={t.label} theme={theme} label={t.label} value={t.value} />
            ))}
          </View>

          <View style={styles.dividerRow}>
            <View style={[styles.divider, { backgroundColor: theme.BORDER }]} />
          </View>

          {/* Segments + signals */}
          <View style={styles.kvGrid}>
            <View style={styles.kvCol}>
              <Text style={[styles.kvHeader, { color: theme.TEXT }]}>Segments</Text>
              {model.kpis.segments.map((s) => (
                <View key={s.label} style={styles.kvRow}>
                  <Text style={[styles.kvLabel, { color: theme.MUTED }]}>{s.label}</Text>
                  <Text style={[styles.kvValue, { color: theme.TEXT }]}>{s.value}</Text>
                </View>
              ))}
            </View>

            <View style={styles.kvCol}>
              <Text style={[styles.kvHeader, { color: theme.TEXT }]}>Market signals</Text>
              {model.kpis.signals.map((sig) => (
                <View key={sig.label} style={styles.kvRow}>
                  <Text style={[styles.kvLabel, { color: theme.MUTED }]}>{sig.label}</Text>
                  <Text style={[styles.kvValue, { color: theme.TEXT }]}>{sig.value}</Text>
                </View>
              ))}
            </View>
          </View>
        </View>

        {/* Highlighted collections carousel */}
        <Section
          title="Highlighted collections"
          theme={theme}
          right={
            <View style={[styles.badge, { borderColor: theme.BORDER, backgroundColor: theme.BG }]}>
              <Ionicons name="sparkles-outline" size={14} color={theme.MUTED} style={{ marginRight: 6 }} />
              <Text style={[styles.badgeText, { color: theme.MUTED }]}>Curated</Text>
            </View>
          }
        >
          <Text style={[styles.sectionHint, { color: theme.MUTED }]}>
            Rotating highlights — like Brand Store shelves: core lines, premium picks, and niche segments.
          </Text>

          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingTop: 12 }}>
            {model.highlights.map((h) => (
              <Pressable
                key={h.id}
                onPress={() =>
                  router.push({
                    pathname: "/chat/category/[categoryId]" as any,
                    params: { categoryId: String(categoryId ?? "") },
                  } as any)
                }
                style={[styles.highlightCard, { width: CARD_W, backgroundColor: theme.BG, borderColor: theme.BORDER }]}
                accessibilityRole="button"
              >
                <View style={styles.highlightTop}>
                  <View style={[styles.highlightDot, { backgroundColor: theme.ACCENT }]} />
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.highlightTitle, { color: theme.TEXT }]} numberOfLines={1}>
                      {h.title}
                    </Text>
                    <Text style={[styles.highlightSub, { color: theme.MUTED }]} numberOfLines={2}>
                      {h.subtitle}
                    </Text>
                  </View>

                  {h.badge ? (
                    <View style={[styles.pill, { borderColor: theme.BORDER, backgroundColor: theme.CARD }]}>
                      <Text style={[styles.pillText, { color: theme.TEXT }]}>{h.badge}</Text>
                    </View>
                  ) : null}
                </View>

                <View style={styles.highlightStatsRow}>
                  {h.stats.map((st) => (
                    <View key={st.label} style={[styles.miniStat, { borderColor: theme.BORDER, backgroundColor: theme.CARD }]}>
                      <Text style={[styles.miniStatValue, { color: theme.TEXT }]}>{st.value}</Text>
                      <Text style={[styles.miniStatLabel, { color: theme.MUTED }]}>{st.label}</Text>
                    </View>
                  ))}
                </View>

                <View style={{ marginTop: 10 }}>
                  {h.bullets.slice(0, 3).map((b, idx) => (
                    <View key={idx} style={styles.bulletRow}>
                      <Ionicons name="checkmark-circle-outline" size={14} color={theme.MUTED} style={{ marginRight: 8 }} />
                      <Text style={[styles.bulletText, { color: theme.MUTED }]} numberOfLines={2}>
                        {b}
                      </Text>
                    </View>
                  ))}
                </View>

                <View style={styles.highlightFooter}>
                  <Text style={[styles.footerHint, { color: theme.MUTED }]}>Open category chat</Text>
                  <Ionicons name="chevron-forward" size={16} color={theme.MUTED} />
                </View>
              </Pressable>
            ))}
            <View style={{ width: 8 }} />
          </ScrollView>
        </Section>

        <Section title="What to collect" theme={theme}>
          {model.copy.whatToCollect.map((x, i) => (
            <View key={i} style={styles.bulletRow}>
              <Ionicons name="radio-button-on-outline" size={14} color={theme.MUTED} style={{ marginRight: 8 }} />
              <Text style={[styles.body, { color: theme.MUTED }]}>{x}</Text>
            </View>
          ))}
        </Section>

        <Section title="How to spot value" theme={theme}>
          {model.copy.howToSpotValue.map((x, i) => (
            <View key={i} style={styles.bulletRow}>
              <Ionicons name="analytics-outline" size={14} color={theme.MUTED} style={{ marginRight: 8 }} />
              <Text style={[styles.body, { color: theme.MUTED }]}>{x}</Text>
            </View>
          ))}
        </Section>

        <View style={[styles.footerCard, { backgroundColor: theme.CARD, borderColor: theme.BORDER }]}>
          <Text style={[styles.footerTitle, { color: theme.TEXT }]}>Next step</Text>
          <Text style={[styles.footerBody, { color: theme.MUTED }]}>
            These are professional placeholders. Next we can wire real aggregates (counts + signals) from your backend.
          </Text>

          <View style={{ flexDirection: "row", gap: 10, marginTop: 12, flexWrap: "wrap" }}>
            <Pressable
              onPress={() =>
                router.push({
                  pathname: "/chat/category/[categoryId]" as any,
                  params: { categoryId: String(categoryId ?? "") },
                } as any)
              }
              style={[styles.primaryBtn, { backgroundColor: theme.ACCENT }]}
              accessibilityRole="button"
            >
              <Ionicons name="chatbubble-ellipses-outline" size={16} color={theme.NAVY} style={{ marginRight: 8 }} />
              <Text style={[styles.primaryBtnText, { color: theme.NAVY }]}>Join category chat</Text>
            </Pressable>

            <Pressable
              onPress={() => router.back()}
              style={[styles.secondaryBtn, { borderColor: theme.BORDER, backgroundColor: theme.CARD }]}
              accessibilityRole="button"
            >
              <Ionicons name="arrow-back-outline" size={16} color={theme.MUTED} style={{ marginRight: 8 }} />
              <Text style={[styles.secondaryBtnText, { color: theme.MUTED }]}>Back</Text>
            </Pressable>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { backgroundColor: '#FFFFFF', flex: 1},

  topBar: { flexDirection: "row", alignItems: "center", marginBottom: 12 },
  iconBtn: { width: 38, height: 38, borderRadius: 12, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  topTitle: { fontSize: 16, fontWeight: "900" },
  topSub: { marginTop: 2, fontSize: 11, fontWeight: "700" },

  hero: { borderWidth: 1, borderRadius: 16, padding: 14, marginBottom: 12 },
  heroRow: { flexDirection: "row", alignItems: "flex-start", gap: 12 },
  heroMark: { width: 10, height: 46, borderRadius: 6, marginTop: 2 },
  heroTitle: { fontSize: 18, fontWeight: "950", letterSpacing: -0.2 },
  heroDesc: { marginTop: 6, fontSize: 12, lineHeight: 17, fontWeight: "650" },

  metricsRow: { marginTop: 12, flexDirection: "row", gap: 10, flexWrap: "wrap" },
  metricChip: { borderWidth: 1, borderRadius: 14, paddingVertical: 10, paddingHorizontal: 12, minWidth: 110 },
  metricValue: { fontSize: 14, fontWeight: "950" },
  metricLabel: { marginTop: 2, fontSize: 11, fontWeight: "750" },

  dividerRow: { marginTop: 12, marginBottom: 6 },
  divider: { height: 1, opacity: 0.9 },

  kvGrid: { marginTop: 8, flexDirection: "row", gap: 12, flexWrap: "wrap" },
  kvCol: { flex: 1, minWidth: 160 },
  kvHeader: { fontSize: 12, fontWeight: "900", marginBottom: 6 },
  kvRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingVertical: 4 },
  kvLabel: { fontSize: 11, fontWeight: "750" },
  kvValue: { fontSize: 11, fontWeight: "900" },

  sectionCard: { borderWidth: 1, borderRadius: 16, padding: 14, marginBottom: 12 },
  sectionHeader: { flexDirection: "row", alignItems: "center" },
  sectionTitle: { fontSize: 14, fontWeight: "950" },
  sectionHint: { marginTop: 8, fontSize: 12, lineHeight: 16, fontWeight: "650" },

  badge: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6, flexDirection: "row", alignItems: "center" },
  badgeText: { fontSize: 11, fontWeight: "850" },

  highlightCard: { borderWidth: 1, borderRadius: 16, padding: 14, marginRight: 12 },
  highlightTop: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
  highlightDot: { width: 10, height: 10, borderRadius: 6, marginTop: 5 },
  highlightTitle: { fontSize: 14, fontWeight: "950" },
  highlightSub: { marginTop: 4, fontSize: 12, lineHeight: 16, fontWeight: "650" },

  pill: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6 },
  pillText: { fontSize: 11, fontWeight: "900" },

  highlightStatsRow: { marginTop: 12, flexDirection: "row", gap: 10, flexWrap: "wrap" },
  miniStat: { borderWidth: 1, borderRadius: 14, paddingVertical: 10, paddingHorizontal: 12, minWidth: 92 },
  miniStatValue: { fontSize: 12, fontWeight: "950" },
  miniStatLabel: { marginTop: 2, fontSize: 10, fontWeight: "750" },

  bulletRow: { marginTop: 8, flexDirection: "row", alignItems: "flex-start" },
  bulletText: { fontSize: 12, lineHeight: 16, fontWeight: "650", flex: 1 },
  body: { fontSize: 12, lineHeight: 16, fontWeight: "650", flex: 1 },

  highlightFooter: { marginTop: 12, flexDirection: "row", alignItems: "center" },
  footerHint: { fontSize: 11, fontWeight: "800", flex: 1 },

  footerCard: { borderWidth: 1, borderRadius: 16, padding: 14, marginBottom: 12 },
  footerTitle: { fontSize: 14, fontWeight: "950" },
  footerBody: { marginTop: 6, fontSize: 12, lineHeight: 17, fontWeight: "650" },

  primaryBtn: { borderRadius: 14, paddingVertical: 12, paddingHorizontal: 14, flexDirection: "row", alignItems: "center" },
  primaryBtnText: { fontSize: 12, fontWeight: "950" },

  secondaryBtn: { borderRadius: 14, borderWidth: 1, paddingVertical: 12, paddingHorizontal: 14, flexDirection: "row", alignItems: "center" },
  secondaryBtnText: { fontSize: 12, fontWeight: "900" },
});
