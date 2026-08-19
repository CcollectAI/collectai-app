/**
 * Help index — every "how do I…" in one list.
 *
 * The browsable half of the help system; the searchable half is in
 * `app/search.tsx`, which matches the same topics via `searchAppHelp`. Both
 * read `src/data/appHelp.ts`, so there is one set of answers rather than two
 * that drift.
 */
import React from 'react';
import { ScrollView, View, Text, StyleSheet, Animated } from 'react-native';
import { Stack, useRouter, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { APP_HELP } from '@/data/appHelp';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';

function HelpIndexScreen() {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const router = useRouter();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerTitle: '' }} />
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Animated.View style={animatedStyle}>
          <View style={[styles.hero, { backgroundColor: colors.accent + '14', borderColor: colors.accent + '33' }]}>
            <Text style={[styles.eyebrow, { color: colors.muted }]}>Need a helping hand?</Text>
            <Text style={[styles.title, { color: colors.text }]}>Using Sparrow</Text>
            <Text style={[styles.summary, { color: colors.muted }]}>
              Short answers to the things people ask first. You can also just
              type what you are trying to do into the search bar.
            </Text>
          </View>

          {APP_HELP.map((topic) => (
            <AnimatedPressable
              key={topic.id}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                router.push(`/help/${topic.id}` as Href);
              }}
              style={[styles.row, { backgroundColor: colors.card, borderColor: colors.border }]}
              accessibilityRole="button"
              accessibilityLabel={topic.title}
            >
              <View style={styles.rowText}>
                <Text style={[styles.rowTitle, { color: colors.text }]}>{topic.title}</Text>
                <Text style={[styles.rowSummary, { color: colors.muted }]} numberOfLines={2}>
                  {topic.summary}
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            </AnimatedPressable>
          ))}
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

export default function HelpIndexScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="HelpIndex">
      <HelpIndexScreen />
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
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    padding: 14,
    marginBottom: 10,
  },
  rowText: { flex: 1, gap: 3 },
  rowTitle: { fontSize: textToken.lg, fontWeight: fontWeight.semibold, lineHeight: 21 },
  rowSummary: { fontSize: textToken.md, lineHeight: 19 },
});
