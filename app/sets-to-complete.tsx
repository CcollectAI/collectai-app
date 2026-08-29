import React, { useEffect, useMemo, useState } from "react";
import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import { QuickNavBar } from "@/components/QuickNavBar";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter, useLocalSearchParams } from "expo-router";
import { getPortfolioItems } from "@/api/portfolioApi";
import type {
  RawPortfolioItem,
  RawPortfolioItemsResponse,
} from "@/../types/api";
import {
  CollectionStatusInput,
  computeCollectionStatusScores,
  SizedCollectionScore,
  hasKnownSetSize,
} from "@/utils/statusScoring";
import logger from "@/utils/logger";
import { formatPrice } from "@/lib/format";
import { useAppTheme } from "@/hooks/useAppTheme";
import { useBillingLimits } from "@/hooks/useBillingLimits";
import { useSettings } from "@/lib/settings";
import {
  SET_TRACKING_CATEGORY_LABELS,
  unsupportedSetCategories,
} from "@/constants/setTracking";
import { ProgressRing } from "@/components/ProgressRing";
import { UpgradePrompt } from "@/components/UpgradePrompt";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";

const MIN_COMPLETENESS = 0.4;
const MAX_COMPLETENESS = 0.95;

type Bucket = {
  key: "almost" | "progress" | "starting";
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  iconTint: string;
  // Sized, not plain: everything in a bucket has already passed
  // `hasKnownSetSize`, and the rows below render a percentage and an
  // "owned of expected" count that only exist for those.
  items: SizedCollectionScore[];
};

const SetsToCompleteScreen: React.FC = () => {
  const { colors } = useAppTheme();
  /**
   * Optional category scope. The screen was global — every unfinished set in
   * the whole portfolio — and reachable from nowhere. Its entry point is now
   * the CATEGORY page, where "what am I still missing" means "in this
   * category", so it accepts a slug and filters to it.
   *
   * Optional, not required: the global view is still valid and still the
   * behaviour on a bare /sets-to-complete deep link.
   */
  const { categoryId } = useLocalSearchParams<{ categoryId?: string }>();
  const { limits } = useBillingLimits();
  const { settings } = useSettings();
  const router = useRouter();
  const [items, setItems] = useState<CollectionStatusInput[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const raw = await getPortfolioItems();
        if (cancelled) return;

        // `/portfolio/items` returns `{ items: [...] }`, NOT a bare array. The
        // old client typed it as `PortfolioItem[]`, so `(raw || []).map` was a
        // TypeError on a response that had made it that far — which none ever
        // did, because that client sent no Authorization header and the route
        // 401'd every time. Array form is still accepted in case the endpoint
        // is ever unwrapped.
        const list: RawPortfolioItem[] = Array.isArray(raw)
          ? (raw as RawPortfolioItem[])
          : ((raw as RawPortfolioItemsResponse | null)?.items ?? []);

        const mapped: CollectionStatusInput[] = list.map(
          (it: RawPortfolioItem) => ({
            id: it.id ?? (it.item_id as string | undefined) ?? undefined,
            name: it.name ?? (it.title as string | null) ?? null,
            title: (it.title as string | null) ?? it.name ?? null,
            category:
              it.category ?? (it.category_label as string | null) ?? null,
            // `/portfolio/items` returns `current_value` — it returns neither
            // `estimated_value` nor `value`, so this read null for every item and
            // the screen's "Est. value" always showed 0. current_value IS the
            // canonical valuation expression
            // COALESCE(l.q50, quick_predictions.q50_eur, predicted_price_eur,
            //          estimated_value, 0)
            // (portfolio_router.py:267), the same one Home and the Items tab use,
            // so reading it here also keeps this screen consistent with them.
            // The other two are kept as fallbacks for callers passing a different
            // item shape.
            value:
              typeof it.current_value === "number"
                ? it.current_value
                : typeof it.estimated_value === "number"
                  ? it.estimated_value
                  : ((it.value as number | null) ?? null),
            collection:
              (it.collection as string | null) ??
              (it.set_name as string | null) ??
              null,
            collection_name:
              (it.collection_name as string | null) ??
              (it.collection as string | null) ??
              null,
            set_code: (it.set_code as string | null) ?? null,
            set_size: (it.set_size as number | null) ?? null,
            rarity_score: (it.rarity_score as number | null) ?? null,
          }),
        );

        setItems(mapped);
      } catch (e: unknown) {
        logger.error("[SetsToComplete] load error", e);
        if (!cancelled) setError("Could not load items.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  /**
   * Categories the member owns that set tracking cannot cover.
   *
   * Drives the empty state. Without this the screen told a whiskey or LEGO
   * collector to "add more items", which is false instruction — their
   * catalogue carries no set names (measured 0.0%, zero rows), so no amount of
   * adding can ever produce a set. They are also PAYING for this screen, which
   * is what makes a vague empty state a broken promise rather than a rough
   * edge (learning_a_written_promise_to_users_is_a_spec).
   */
  /**
   * SCOPED, when a category was passed. Everything below reasons about "what
   * can this screen show you", and in a category-scoped view that question is
   * about your items IN THAT CATEGORY — not your whole portfolio.
   *
   * Reading the unscoped list here produced a false sentence: open "Finish a
   * set" from a category you own nothing in, and the screen said "Scan or add
   * more items to start tracking which collections you're close to finishing",
   * which implies you have some here and are merely not close. The true
   * sentence is that you own nothing in this category yet. Same defect the
   * whiskey/LEGO branch below was written to fix, one scope out.
   */
  const scopedItems = useMemo(
    () => (categoryId ? items.filter((it) => it.category === categoryId) : items),
    [items, categoryId],
  );
  const uncoveredCategories = useMemo(
    () => unsupportedSetCategories(scopedItems),
    [scopedItems],
  );
  const hasOnlyUncovered =
    scopedItems.length > 0 && uncoveredCategories.length > 0 &&
    scopedItems.every((it) => !it.category || uncoveredCategories.includes(
      it.category.trim().toLowerCase(),
    ));
  /** Nothing owned HERE — distinct from "owned, but no set is near done". */
  const ownsNothingInScope = Boolean(categoryId) && scopedItems.length === 0 && items.length >= 0;

  const candidates: SizedCollectionScore[] = useMemo(() => {
    if (!items.length) return [];
    const scores = computeCollectionStatusScores(items);
    return (
      scores
        // A set whose size we do not know cannot be reported as partly finished,
        // so it is not a candidate at all. This is a real filter now: until
        // 2026-08-15 an unknown size defaulted to "expected = what you own",
        // every set scored exactly 1.0, and the band below then removed ALL of
        // them — the screen was empty for every account. See `hasKnownSetSize`.
        .filter(hasKnownSetSize)
        .filter(
          (s) =>
            // Category scope, when one was passed. A set whose category is null
            // is dropped from a scoped view rather than kept: "unknown" is not
            // "this one", and showing it under a category heading would assert
            // something we do not know.
            (!categoryId || s.category === categoryId) &&
            s.completenessRatio >= MIN_COMPLETENESS &&
            s.completenessRatio <= MAX_COMPLETENESS,
        )
        .sort(
          (a, b) =>
            b.completenessRatio - a.completenessRatio ||
            b.valueTotal - a.valueTotal,
        )
    );
  }, [items, categoryId]);

  const summary = useMemo(
    () => ({
      sets: candidates.length,
      missing: candidates.reduce(
        (s, c) => s + Math.max(0, c.expectedCount - c.ownedCount),
        0,
      ),
      value: candidates.reduce((s, c) => s + c.valueTotal, 0),
    }),
    [candidates],
  );

  const buckets: Bucket[] = useMemo(
    () => [
      {
        key: "almost",
        label: "Almost there",
        icon: "flame" as const,
        iconTint: "#F97316",
        items: candidates.filter((s) => s.completenessRatio >= 0.8),
      },
      {
        key: "progress",
        label: "Making progress",
        icon: "trending-up" as const,
        iconTint: colors.accent,
        items: candidates.filter(
          (s) => s.completenessRatio >= 0.6 && s.completenessRatio < 0.8,
        ),
      },
      {
        key: "starting",
        label: "Getting started",
        icon: "sparkles-outline" as const,
        iconTint: colors.muted,
        items: candidates.filter((s) => s.completenessRatio < 0.6),
      },
    ],
    [candidates, colors.accent, colors.muted],
  );

  const openCollection = (collectionName: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, {
      enabled: settings.hapticsEnabled,
    });
    router.push({
      // `collectionName`, not `collection`. app/(tabs)/items.tsx reads
      // `{ category?, collectionName? }`, so the old key was dropped in transit
      // and the screen opened unfiltered — silently, because expo-router types
      // params as an open record and accepts any key (check-route-param-handoff).
      pathname: "/(tabs)/items",
      params: { collectionName },
    });
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text style={[styles.title, { color: colors.text }]}>
          Sets to complete
        </Text>
        <Text style={[styles.subtitle, { color: colors.muted }]}>
          Collections close to 100%. Sorted by what you&apos;re nearest to
          finishing.
        </Text>

        {/* Summary card — only shown when we have candidates to summarise */}
        {!loading &&
          !error &&
          limits.set_completion &&
          candidates.length > 0 && (
            <View
              style={[
                styles.summaryCard,
                { backgroundColor: colors.card, borderColor: colors.border },
              ]}
            >
              <SummaryStat
                label="Sets"
                value={String(summary.sets)}
                tint={colors.text}
              />
              <View
                style={[
                  styles.summaryDivider,
                  { backgroundColor: colors.border },
                ]}
              />
              <SummaryStat
                label="Missing"
                value={String(summary.missing)}
                tint={colors.warning}
              />
              <View
                style={[
                  styles.summaryDivider,
                  { backgroundColor: colors.border },
                ]}
              />
              <SummaryStat
                label="Est. value"
                value={formatPrice(summary.value)}
                tint={colors.accent}
              />
            </View>
          )}

        {loading && (
          <View style={styles.center}>
            <ActivityIndicator />
          </View>
        )}

        {!loading && error && (
          <View style={styles.center}>
            <Text style={[styles.error, { color: colors.danger }]}>
              {error}
            </Text>
          </View>
        )}

        {!loading && !error && !limits.set_completion && (
          <View style={styles.gatedWrap}>
            <UpgradePrompt
              feature="Set Completion Tracking"
              requiredPlan="Pro"
            />
          </View>
        )}

        {!loading &&
          !error &&
          limits.set_completion &&
          candidates.length === 0 && (
            <View style={styles.emptyCard}>
              <Ionicons name="cube-outline" size={36} color={colors.muted} />
              <Text style={[styles.emptyTitle, { color: colors.text }]}>
                {ownsNothingInScope
                  ? "You don't have any items in this category yet"
                  : hasOnlyUncovered
                    ? "Set tracking doesn't cover these categories yet"
                    : "No sets near completion yet"}
              </Text>
              <Text style={[styles.empty, { color: colors.muted }]}>
                {ownsNothingInScope
                  ? "This screen shows what you're still missing from sets you've already started, so it needs at least two items from one set. Add something in this category and it will start tracking."
                  : hasOnlyUncovered
                    ? `Progress needs a set list — how many pieces make a full set — and we only have those for ${SET_TRACKING_CATEGORY_LABELS} today. Your ${uncoveredCategories
                        .slice(0, 3)
                        .map((c) => c.replace(/_/g, " "))
                        .join(", ")} items aren't covered, so adding more won't change this screen.`
                    : "Scan or add more items to start tracking which collections you're close to finishing."}
              </Text>
            </View>
          )}

        {!loading &&
          !error &&
          limits.set_completion &&
          buckets.map((bucket) => {
            if (bucket.items.length === 0) return null;
            return (
              <View key={bucket.key} style={styles.bucketWrap}>
                <View style={styles.bucketHeader}>
                  <Ionicons
                    name={bucket.icon}
                    size={16}
                    color={bucket.iconTint}
                  />
                  <Text style={[styles.bucketLabel, { color: colors.text }]}>
                    {bucket.label}
                  </Text>
                  <View
                    style={[
                      styles.bucketCount,
                      { backgroundColor: colors.border + "66" },
                    ]}
                  >
                    <Text
                      style={[styles.bucketCountText, { color: colors.muted }]}
                    >
                      {bucket.items.length}
                    </Text>
                  </View>
                </View>

                {bucket.items.map((s) => {
                  const missing = Math.max(0, s.expectedCount - s.ownedCount);
                  const pct = Math.round(s.completenessRatio * 100);
                  const ringColor =
                    s.completenessRatio >= 0.8 ? "#0BA86C" : colors.accent;
                  return (
                    <AnimatedPressable
                      key={s.key}
                      onPress={() => openCollection(s.key)}
                      style={[
                        styles.card,
                        {
                          backgroundColor: colors.card,
                          borderColor: colors.border,
                        },
                      ]}
                      accessibilityRole="button"
                      accessibilityLabel={`${s.key}, ${pct}% complete, ${missing} missing`}
                    >
                      <ProgressRing
                        progress={s.completenessRatio}
                        size={54}
                        strokeWidth={6}
                        progressColor={ringColor}
                      />
                      <View style={styles.cardBody}>
                        <Text
                          style={[styles.cardTitle, { color: colors.text }]}
                          numberOfLines={1}
                        >
                          {s.key}
                        </Text>
                        <Text
                          style={[styles.cardMeta, { color: colors.muted }]}
                        >
                          {s.category ? `${s.category} · ` : ""}
                          {s.ownedCount}/{s.expectedCount} owned
                        </Text>
                        <View style={styles.pillRow}>
                          <View
                            style={[
                              styles.pill,
                              { backgroundColor: colors.warning + "18" },
                            ]}
                          >
                            <Text
                              style={[
                                styles.pillText,
                                { color: colors.warning },
                              ]}
                            >
                              {missing} missing
                            </Text>
                          </View>
                          <View
                            style={[
                              styles.pill,
                              { backgroundColor: colors.accent + "15" },
                            ]}
                          >
                            <Text
                              style={[
                                styles.pillText,
                                { color: colors.accent },
                              ]}
                            >
                              {formatPrice(s.valueTotal)}
                            </Text>
                          </View>
                        </View>
                      </View>
                      <View style={styles.cardTrailing}>
                        <Text style={[styles.cardPct, { color: ringColor }]}>
                          {pct}%
                        </Text>
                        <Ionicons
                          name="chevron-forward"
                          size={16}
                          color={colors.muted}
                        />
                      </View>
                    </AnimatedPressable>
                  );
                })}
              </View>
            );
          })}
      </ScrollView>
      <QuickNavBar />
    </View>
  );
};

const SummaryStat: React.FC<{ label: string; value: string; tint: string }> = ({
  label,
  value,
  tint,
}) => {
  const { colors } = useAppTheme();
  return (
    <View style={styles.summaryStat}>
      <Text style={[styles.summaryValue, { color: tint }]}>{value}</Text>
      <Text style={[styles.summaryLabel, { color: colors.muted }]}>
        {label}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: {
    paddingHorizontal: 16,
    // 16, matching the gutter and the help/guide screens. Was 12, which set
    // the title a notch tighter to the header than every other screen.
    paddingTop: 16,
    paddingBottom: 40,
  },
  // The gated state renders UpgradePrompt, whose container carries only a
  // marginBottom — so it butted straight against the subtitle while every
  // sibling block (center, emptyCard, summaryCard) has its own top gap.
  gatedWrap: {
    marginTop: 24,
  },
  center: {
    marginTop: 24,
    alignItems: "center",
  },
  title: {
    fontSize: 24,
    fontWeight: "800",
    lineHeight: 30,
  },
  subtitle: {
    marginTop: 4,
    fontSize: 12,
  },
  summaryCard: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 12,
    borderWidth: 1,
    paddingVertical: 14,
    marginTop: 14,
    marginBottom: 4,
  },
  summaryStat: {
    flex: 1,
    alignItems: "center",
  },
  summaryValue: {
    fontSize: 20,
    fontWeight: "800",
  },
  summaryLabel: {
    marginTop: 2,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  summaryDivider: {
    width: 1,
    height: 28,
  },
  error: { fontSize: 13 },
  emptyCard: {
    marginTop: 24,
    paddingVertical: 24,
    paddingHorizontal: 16,
    alignItems: "center",
    gap: 8,
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: "700",
  },
  empty: {
    fontSize: 12,
    textAlign: "center",
    paddingHorizontal: 16,
    lineHeight: 17,
  },
  bucketWrap: {
    marginTop: 18,
  },
  bucketHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 8,
  },
  bucketLabel: {
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 0.2,
  },
  bucketCount: {
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 10,
  },
  bucketCountText: {
    fontSize: 11,
    fontWeight: "700",
  },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    marginTop: 8,
  },
  cardBody: {
    flex: 1,
    gap: 3,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: "700",
  },
  cardMeta: {
    fontSize: 11,
  },
  pillRow: {
    flexDirection: "row",
    gap: 6,
    marginTop: 4,
  },
  pill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  pillText: {
    fontSize: 11,
    fontWeight: "600",
  },
  cardTrailing: {
    alignItems: "flex-end",
    gap: 2,
  },
  cardPct: {
    fontSize: 14,
    fontWeight: "800",
  },
});

export default function SetsToCompleteScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Sets to Complete">
      <SetsToCompleteScreen />
    </ScreenErrorBoundary>
  );
}
