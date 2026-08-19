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

import { useAppTheme } from '@/hooks/useAppTheme';
import { useEnterReveal } from '@/motion';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { EmptyState } from '@/components/EmptyState';
import { guideFor } from '@/data/collectingGuides';
import { getCategoryById, CATEGORY_VISUAL, type CategoryId } from '@/data/categories';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';

/** One titled block. Kept local: every section on this page is prose in a box,
 *  and six near-identical inline Views is how a screen drifts out of alignment
 *  with itself.
 *
 *  `emphasis` exists because six boxes of identical weight read as six equally
 *  important things, which is the "three equal controls read as three equal
 *  decisions" lesson from docs/ui-playbook.md applied to prose. The page has
 *  exactly one section that stops a beginner losing money and two that are the
 *  payoff; the rest is reference. Three levels, not one:
 *
 *    'plain'  reference — glossary, care, value drivers
 *    'pick'   the payoff — grail and entry point, tinted and rule-marked
 *    'alert'  the warning — tinted fill, so it cannot be skimmed past
 */
function Section({
  title,
  tone,
  emphasis = 'plain',
  children,
  colors,
}: {
  title: string;
  /** Border + icon colour. Care is calm, risk is loud, value is neutral. */
  tone: string;
  emphasis?: 'plain' | 'pick' | 'alert';
  children: React.ReactNode;
  colors: ReturnType<typeof useAppTheme>['colors'];
}) {
  return (
    <View
      style={[
        styles.section,
        {
          // The tone at 10% alpha, never the tone itself: text stays on theme
          // colours, so nothing here can go invisible when the palette swaps
          // (docs/ui-playbook.md, "Never hardcode a colour on a themed
          // background"). A tint is decoration; the contrast is still the
          // theme's job.
          backgroundColor: emphasis === 'plain' ? colors.card : tone + '12',
          borderColor: emphasis === 'plain' ? colors.border : tone + '40',
        },
        // A left rule on the two sections that carry a specific thing rather
        // than general guidance — the eye finds them when scrolling back.
        emphasis === 'pick' ? { borderLeftWidth: 3, borderLeftColor: tone } : null,
      ]}
    >
      {/* No icon. A coloured glyph in a tinted disc beside every heading is
          template styling — it decorates six headings identically and so
          distinguishes none of them, which is what the tint and the left rule
          already do properly. The heading is the heading. */}
      <Text style={[styles.sectionTitle, { color: tone }]}>{title}</Text>
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
  // The category's own colour and glyph, used ONLY as a tint and a small icon.
  // Falls back to the brand accent for a guide whose slug has no visual entry,
  // so a missing key is a duller header rather than a crash.
  const visual = categoryId ? CATEGORY_VISUAL[categoryId as CategoryId] : undefined;
  const heroTint = visual?.accentColor ?? colors.accent;

  // A guide that does not exist is reachable only by hand-typed URL or a stale
  // deep link — the CTA is never rendered without one. Say so plainly rather
  // than showing an empty page that looks broken.
  if (!guide) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <Stack.Screen options={{ headerTitle: '' }} />
        <EmptyState
          icon="book-outline"
          title="No guide for this category yet"
          subtitle="We have starter guides for a handful of categories so far. More are coming."
          colors={colors}
        />
        <QuickNavBar />
      </View>
    );
  }

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerTitle: '' }} />
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Animated.View style={animatedStyle}>
          {/* A hero rather than a bare heading. The page used to open with
              plain text on plain background, which made a six-section guide
              read as a wall from the first pixel. The tint is the CATEGORY's
              own colour at 14% — the same device the category screen's "New to
              this?" banner uses — so Pokémon and Warhammer guides do not look
              like the same page, while every glyph and letter stays on a theme
              colour. */}
          <View
            style={[
              styles.hero,
              { backgroundColor: heroTint + '14', borderColor: heroTint + '33' },
            ]}
          >
            {/* Friendly, and a question rather than a label. "BEGINNER GUIDE"
                is a filing category; this is how you would open if somebody
                asked you about their first Lorcana pack across a table. */}
            <Text style={[styles.heroEyebrow, { color: colors.muted }]}>
              Need a helping hand?
            </Text>
            <Text style={[styles.title, { color: colors.text }]}>
              Starting out in {title}
            </Text>
            <Text style={[styles.intro, { color: colors.muted }]}>{guide.intro}</Text>
          </View>

          {/* First, and only where it exists. "Warhammer" and "Lorcana" mean
              nothing until somebody says what they are, while a watch guide
              opening with a paragraph on what a watch is would read as padding.
              Every section below this one assumes you already know. */}
          {guide.whatItIs ? (
            <Section title="Background" tone={colors.accent} colors={colors}>
              {/* Split on blank lines. The most-collected categories carry a
                  multi-paragraph primer (2026-08-16) and a single <Text> ran
                  them together into one wall — a beginner reading four
                  paragraphs about eras, formats and vocabulary needs the
                  breaks to be able to stop and re-read one. */}
              {guide.whatItIs.split(/\n\s*\n/).map((para, i) => (
                <Text
                  key={i}
                  style={[styles.body, { color: colors.muted }, i > 0 && styles.bodyNext]}
                >
                  {para.trim()}
                </Text>
              ))}
            </Section>
          ) : null}

          <Section title="Words you'll see" tone={colors.accent} colors={colors}>
            {/* A hairline between entries, and none after the last one. Three
                term/definition pairs with only a 2pt gap read as one paragraph
                with some bold words in it. */}
            {guide.glossary.map((g, i) => (
              <View
                key={g.term}
                style={[
                  styles.term,
                  i < guide.glossary.length - 1
                    ? { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border, paddingBottom: 10 }
                    : null,
                ]}
              >
                <Text style={[styles.termName, { color: colors.text }]}>{g.term}</Text>
                <Text style={[styles.body, { color: colors.muted }]}>{g.definition}</Text>
              </View>
            ))}
          </Section>

          <Section title="Looking after it" tone={colors.success} colors={colors}>
            <Text style={[styles.body, { color: colors.muted }]}>{guide.care}</Text>
          </Section>

          {/* Loud on purpose: this is the section that stops a beginner losing
              money, and it is the one they will skip if it looks like the rest. */}
          <Section title={guide.watchOut.title} tone={colors.danger} emphasis="alert" colors={colors}>
            <Text style={[styles.body, { color: colors.muted }]}>{guide.watchOut.body}</Text>
          </Section>

          <Section title="What drives value" tone={colors.accent} colors={colors}>
            <Text style={[styles.body, { color: colors.muted }]}>{guide.valueDrivers}</Text>
          </Section>

          <Section title="The one everyone wants" tone={colors.warning} emphasis="pick" colors={colors}>
            <Text style={[styles.pickTitle, { color: colors.text }]}>{guide.holyGrail.title}</Text>
            <Text style={[styles.body, { color: colors.muted }]}>{guide.holyGrail.why}</Text>
          </Section>

          {/* Last, and deliberately so — the page ends on something affordable
              rather than on a five-figure grail. */}
          <Section title="Where to start" tone={colors.success} emphasis="pick" colors={colors}>
            <Text style={[styles.pickTitle, { color: colors.text }]}>{guide.entryLevel.title}</Text>
            <Text style={[styles.body, { color: colors.muted }]}>{guide.entryLevel.why}</Text>
          </Section>

          <Text style={[styles.footnote, { color: colors.muted }]}>
            General guidance, not valuation advice. Prices move and condition is
            judged by whoever is buying.
          </Text>
        </Animated.View>
      </ScrollView>
      {/* These three are pushed routes OUTSIDE the (tabs) group, so they get no
          tab bar of their own — and a reader who lands here from search has
          only the back chevron. QuickNavBar is a normal flex row (not
          absolute), so it reserves its own space and the ScrollView above
          needs no extra inset. Added 2026-08-16. */}
      <QuickNavBar />
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
  bodyNext: { marginTop: 12 },
  safe: { flex: 1 },
  content: { padding: 16, paddingBottom: 40 },
  hero: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    padding: 16,
    marginBottom: 16,
  },
  // `sm` (12) with wide tracking — a label, not body copy, and the one place
  // on this page small type is legitimate (docs/ui-playbook.md type scale).
  heroEyebrow: { fontSize: textToken.md, fontWeight: fontWeight.semibold, letterSpacing: 0.1 },
  title: { fontSize: textToken['2xl'], fontWeight: fontWeight.extrabold, lineHeight: 30 },
  intro: { fontSize: textToken.md, lineHeight: 21, marginTop: 8 },
  section: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    padding: 14,
    marginBottom: 12,
    gap: 8,
  },
  sectionHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  // Sentence case at `lg`, not tracked-out caps at `sm`. ALL-CAPS headings
  // read as system labels — fine on a dashboard, wrong on a page whose whole
  // job is to sound like a person explaining something. Wide letter-spacing
  // exists to make caps legible; in sentence case it just looks stretched.
  sectionTitle: {
    fontSize: textToken.lg,
    fontWeight: fontWeight.bold,
    letterSpacing: 0.1,
  },
  term: { gap: 3, paddingTop: 2 },
  termName: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  // `md`, not `sm`: this is body prose a beginner has to read, and the playbook
  // bans anything smaller for text that carries meaning.
  body: { fontSize: textToken.md, lineHeight: 21 },
  pickTitle: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  footnote: { fontSize: textToken.sm, lineHeight: 17, marginTop: 4, fontStyle: 'italic' },
});
