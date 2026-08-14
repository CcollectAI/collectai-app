/**
 * "New to collecting? Start here" — shown only to members who said they are.
 *
 * This is the CONSUMER for `user_settings.skill_level`. Without it the column
 * would be written at onboarding and read by nothing, which is the capture-
 * without-a-consumer shape this codebase keeps writing down.
 *
 * Three conditions, all required:
 *   1. skillLevel === 'beginner'. NOT `!== 'advanced'` — null means "never
 *      asked", and someone who onboarded before the question existed must not
 *      be told they are new to their own hobby.
 *   2. A guide exists to send them to. Only 7 of 56 categories have one, and a
 *      card that opens nothing is worse than no card.
 *   3. They have not dismissed it.
 *
 * Dismissible on purpose. Skill level is answered once at onboarding, and
 * without a way to close this a member who over-corrected would carry a
 * beginner banner on their home screen forever. Dismissal is local — it is a
 * display preference, not something worth a column.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, type Href } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { useFollowedCategories } from '@/hooks/useFollowedCategories';
import { guideFor, GUIDED_CATEGORY_IDS } from '@/data/collectingGuides';
import { getCategoryById } from '@/data/categories';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';
import { logger } from '@/lib/logger';

const DISMISS_KEY = '@sparrowcollect/start_collecting_dismissed';

export function StartCollectingCard() {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { followed } = useFollowedCategories();
  const router = useRouter();
  // `null` while we are still reading storage, so the card cannot flash on and
  // then vanish for someone who dismissed it last week.
  const [dismissed, setDismissed] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(DISMISS_KEY)
      .then((v) => { if (!cancelled) setDismissed(v === 'true'); })
      .catch((e) => {
        logger.error('[startCollecting] dismiss read failed:', e);
        // Failing to read the flag should not hide the card — the worst case is
        // showing it once more, which is far better than silently suppressing
        // the only entry point a beginner has.
        if (!cancelled) setDismissed(false);
      });
    return () => { cancelled = true; };
  }, []);

  const dismiss = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setDismissed(true);
    AsyncStorage.setItem(DISMISS_KEY, 'true').catch((e) =>
      logger.error('[startCollecting] dismiss write failed:', e),
    );
  }, [settings.hapticsEnabled]);

  // Prefer a category they actually follow; fall back to the first guided one
  // so the card is never a dead end for a beginner who skipped the picker.
  const target =
    Array.from(followed).find((slug) => guideFor(slug)) ?? GUIDED_CATEGORY_IDS[0] ?? null;

  if (settings.skillLevel !== 'beginner') return null;
  if (dismissed !== false) return null;
  if (!target) return null;

  const name = getCategoryById(target)?.name ?? 'collecting';

  return (
    <AnimatedPressable
      onPress={() => {
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
        router.push({ pathname: '/guide/[categoryId]', params: { categoryId: target } } as unknown as Href);
      }}
      style={[styles.card, { backgroundColor: colors.accent + '12', borderColor: colors.accent + '3A' }]}
      accessibilityRole="button"
      accessibilityLabel={`Start collecting ${name}: read the beginner guide`}
    >
      <View style={[styles.icon, { backgroundColor: colors.accent + '22' }]}>
        <Ionicons name="school-outline" size={22} color={colors.accent} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={[styles.title, { color: colors.text }]}>New to this? Start here</Text>
        <Text style={[styles.sub, { color: colors.muted }]} numberOfLines={2}>
          A short guide to {name} — the words, what to avoid, and what to buy first.
        </Text>
      </View>
      <AnimatedPressable
        onPress={dismiss}
        hitSlop={10}
        style={styles.close}
        accessibilityRole="button"
        accessibilityLabel="Dismiss this suggestion"
      >
        <Ionicons name="close" size={18} color={colors.muted} />
      </AnimatedPressable>
    </AnimatedPressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginHorizontal: 16,
    marginBottom: 12,
    padding: 12,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
  },
  icon: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  sub: { fontSize: textToken.sm, lineHeight: 17, marginTop: 2 },
  close: { padding: 2 },
});
