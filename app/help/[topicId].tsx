/**
 * One help topic — "how do I…", answered in steps.
 *
 * Content lives in `src/data/appHelp.ts`; this screen only renders it. Sibling
 * of app/guide/[categoryId].tsx and deliberately built the same way, because
 * they are two halves of the same promise: that guide explains the HOBBY, this
 * explains the APP.
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
import { helpTopic } from '@/data/appHelp';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';

function HelpTopicScreen() {
  const { colors } = useAppTheme();
  const { topicId } = useLocalSearchParams<{ topicId?: string }>();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  const topic = helpTopic(topicId);

  // Reachable only by a hand-typed URL or a stale deep link — every entry point
  // is built from the list itself. Say so plainly rather than showing a blank.
  if (!topic) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <Stack.Screen options={{ headerTitle: '' }} />
        <EmptyState
          icon="help-buoy-outline"
          title="We have no help page for that yet"
          subtitle="Try searching for what you are trying to do — the search bar looks in here too."
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
          <View style={[styles.hero, { backgroundColor: colors.accent + '14', borderColor: colors.accent + '33' }]}>
            <Text style={[styles.eyebrow, { color: colors.muted }]}>Need a helping hand?</Text>
            <Text style={[styles.title, { color: colors.text }]}>{topic.title}</Text>
            <Text style={[styles.summary, { color: colors.muted }]}>{topic.summary}</Text>
          </View>

          {/* Numbered, because these are steps in an order — a bulleted list
              would say "any of these", and the second step usually depends on
              the first having happened. */}
          {topic.steps.map((step, i) => (
            <View
              key={step.action}
              style={[styles.step, { backgroundColor: colors.card, borderColor: colors.border }]}
            >
              <View style={styles.stepHead}>
                <View style={[styles.stepNum, { backgroundColor: colors.accent }]}>
                  {/* `accentText`, never a hardcoded white — this sits on an
                      accent fill and the palette swaps underneath it
                      (docs/ui-playbook.md). */}
                  <Text style={[styles.stepNumText, { color: colors.accentText }]}>{i + 1}</Text>
                </View>
                <Text style={[styles.stepAction, { color: colors.text }]}>{step.action}</Text>
              </View>
              {step.detail ? (
                <Text style={[styles.stepDetail, { color: colors.muted }]}>{step.detail}</Text>
              ) : null}
            </View>
          ))}

          {topic.footnote ? (
            <View style={[styles.footnote, { backgroundColor: colors.accent + '10', borderColor: colors.accent + '30' }]}>
              <Text style={[styles.footnoteText, { color: colors.muted }]}>{topic.footnote}</Text>
            </View>
          ) : null}
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

export default function HelpTopicScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="HelpTopic">
      <HelpTopicScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  content: { padding: 16, paddingBottom: 40 },
  hero: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    padding: 16,
    marginBottom: 16,
  },
  eyebrow: { fontSize: textToken.md, fontWeight: fontWeight.semibold, marginBottom: 6 },
  title: { fontSize: textToken['2xl'], fontWeight: fontWeight.extrabold, lineHeight: 30 },
  summary: { fontSize: textToken.md, lineHeight: 21, marginTop: 8 },
  step: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    padding: 14,
    marginBottom: 10,
    gap: 8,
  },
  stepHead: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  stepNum: {
    width: 24, height: 24, borderRadius: 12,
    alignItems: 'center', justifyContent: 'center',
    marginTop: 1,
  },
  stepNumText: { fontSize: textToken.sm, fontWeight: fontWeight.extrabold },
  stepAction: { flex: 1, fontSize: textToken.lg, fontWeight: fontWeight.semibold, lineHeight: 22 },
  // `md`, not `sm`: this is body prose someone has to read, and the playbook
  // bans anything smaller for text that carries meaning.
  stepDetail: { fontSize: textToken.md, lineHeight: 21, marginLeft: 34 },
  footnote: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.md,
    padding: 12,
    marginTop: 4,
  },
  footnoteText: { fontSize: textToken.md, lineHeight: 20 },
});
