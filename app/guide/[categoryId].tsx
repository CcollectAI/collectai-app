/**
 * How to start collecting — one category, one page.
 *
 * Content lives in `src/data/collectingGuides.ts`; this screen only renders it.
 * Most of the 56 categories have no guide, and that is normal rather than a
 * gap: the entry points must branch on `guideFor()` returning null instead of
 * offering a route that opens an empty page.
 *
 * Reached from the category screen's call-to-action, and from the beginner
 * surface for members who said they are just starting.
 *
 * Registered in app/_layout.tsx with `iconOnlyHeader`, whose back button routes
 * through `safeGoBack` — `router.back()` is a silent no-op on an empty stack,
 * which happens on any deep link or push-notification tap (docs/ui-playbook.md).
 */
import React from 'react';
import { ScrollView, View, Text, StyleSheet, Animated } from 'react-native';
import { Stack, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { useAppTheme } from '@/hooks/useAppTheme';
import { useEnterReveal } from '@/motion';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { EmptyState } from '@/components/EmptyState';
import { guideFor } from '@/data/collectingGuides';
import { getCategoryById } from '@/data/categories';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';

/** One titled block. Kept local: every section on this page is prose in a box,
 *  and six near-identical inline Views is how a screen drifts out of alignment
 *  with itself. */
function Section({
  icon,
  title,
  tone,
  children,
  colors,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  /** Border + icon colour. Care is calm, risk is loud, value is neutral. */
  tone: string;
  children: React.ReactNode;
  colors: ReturnType<typeof useAppTheme>['colors'];
}) {
  return (
    <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.sectionHead}>
        <Ionicons name={icon} size={16} color={tone} />
        <Text style={[styles.sectionTitle, { color: tone }]}>{title}</Text>
      </View>
      {children}
    </View>
  );
}

function GuideScreen() {
  const { colors } = useAppTheme();
  const { categoryId } = useLocalSearchParams<{ categoryId?: string }>();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  const guide = guideFor(categoryId);
  const category = categoryId ? getCategoryById(categoryId) : undefined;
  const title = category?.name ?? 'Collecting guide';

  // A guide that does not exist is reachable only by hand-typed URL or a stale
  // deep link — the CTA is never rendered without one. Say so plainly rather
  // than showing an empty page that looks broken.
  if (!guide) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <Stack.Screen options={{ headerTitle: title }} />
        <EmptyState
          icon="book-outline"
          title="No guide for this category yet"
          subtitle="We have starter guides for a handful of categories so far. More are coming."
          colors={colors}
        />
      </View>
    );
  }

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerTitle: title }} />
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Animated.View style={animatedStyle}>
          <Text style={[styles.title, { color: colors.text }]}>
            Starting out in {title}
          </Text>
          <Text style={[styles.intro, { color: colors.muted }]}>{guide.intro}</Text>

          <Section icon="book-outline" title="WORDS YOU WILL SEE" tone={colors.accent} colors={colors}>
            {guide.glossary.map((g) => (
              <View key={g.term} style={styles.term}>
                <Text style={[styles.termName, { color: colors.text }]}>{g.term}</Text>
                <Text style={[styles.body, { color: colors.muted }]}>{g.definition}</Text>
              </View>
            ))}
          </Section>

          <Section icon="shield-checkmark-outline" title="LOOKING AFTER IT" tone={colors.success} colors={colors}>
            <Text style={[styles.body, { color: colors.muted }]}>{guide.care}</Text>
          </Section>

          {/* Loud on purpose: this is the section that stops a beginner losing
              money, and it is the one they will skip if it looks like the rest. */}
          <Section icon="warning-outline" title={guide.watchOut.title.toUpperCase()} tone={colors.danger} colors={colors}>
            <Text style={[styles.body, { color: colors.muted }]}>{guide.watchOut.body}</Text>
          </Section>

          <Section icon="trending-up-outline" title="WHAT DRIVES VALUE" tone={colors.accent} colors={colors}>
            <Text style={[styles.body, { color: colors.muted }]}>{guide.valueDrivers}</Text>
          </Section>

          <Section icon="trophy-outline" title="THE ONE EVERYONE WANTS" tone={colors.warning} colors={colors}>
            <Text style={[styles.pickTitle, { color: colors.text }]}>{guide.holyGrail.title}</Text>
            <Text style={[styles.body, { color: colors.muted }]}>{guide.holyGrail.why}</Text>
          </Section>

          {/* Last, and deliberately so — the page ends on something affordable
              rather than on a five-figure grail. */}
          <Section icon="bulb-outline" title="WHERE TO ACTUALLY START" tone={colors.success} colors={colors}>
            <Text style={[styles.pickTitle, { color: colors.text }]}>{guide.entryLevel.title}</Text>
            <Text style={[styles.body, { color: colors.muted }]}>{guide.entryLevel.why}</Text>
          </Section>

          <Text style={[styles.footnote, { color: colors.muted }]}>
            General guidance, not valuation advice. Prices move and condition is
            judged by whoever is buying.
          </Text>
        </Animated.View>
      </ScrollView>
    </View>
  );
}

export default function GuideScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="CollectingGuide">
      <GuideScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  content: { padding: 16, paddingBottom: 40 },
  title: { fontSize: textToken['2xl'], fontWeight: fontWeight.extrabold, lineHeight: 30 },
  intro: { fontSize: textToken.md, lineHeight: 21, marginTop: 8, marginBottom: 16 },
  section: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    padding: 14,
    marginBottom: 12,
    gap: 8,
  },
  sectionHead: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  sectionTitle: {
    fontSize: textToken.sm,
    fontWeight: fontWeight.extrabold,
    letterSpacing: 0.5,
  },
  term: { gap: 2 },
  termName: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  // `md`, not `sm`: this is body prose a beginner has to read, and the playbook
  // bans anything smaller for text that carries meaning.
  body: { fontSize: textToken.md, lineHeight: 21 },
  pickTitle: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  footnote: { fontSize: textToken.sm, lineHeight: 17, marginTop: 4, fontStyle: 'italic' },
});
