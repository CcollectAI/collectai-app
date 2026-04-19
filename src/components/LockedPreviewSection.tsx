/**
 * LockedPreviewSection — bare upgrade prompt for paywalled sections.
 *
 * Initially (2026-04-18) rendered skeleton silhouettes. Then (earlier on
 * 2026-04-19) was upgraded to realistic mock previews. User feedback
 * 2026-04-19 reverted to a clean bare prompt — real data belongs in the
 * paid view, not a faked preview.
 *
 * To see the paid view as a developer without upgrading, set
 * `EXPO_PUBLIC_FORCE_PLAN=pro` in the .env and restart the dev server.
 */

import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { router, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';

type Props = {
  title: string;
  subtitle?: string;
  // kept for back-compat with existing call sites; no longer renders previews
  previewType?: 'chart' | 'list' | 'report' | 'history';
  requiredPlan?: string;
};

export const LockedPreviewSection = React.memo(function LockedPreviewSection({
  title,
  subtitle,
  requiredPlan = 'Pro',
}: Props) {
  const { colors } = useAppTheme();

  return (
    <View
      style={[
        styles.container,
        { backgroundColor: colors.card, borderColor: colors.border },
      ]}
    >
      <View style={styles.row}>
        <View style={[styles.iconWrap, { backgroundColor: colors.warning + '15' }]}>
          <Ionicons name="lock-closed" size={14} color={colors.warning} />
        </View>
        <View style={styles.text}>
          <Text style={[styles.title, { color: colors.text }]}>{title}</Text>
          <Text style={[styles.subtitle, { color: colors.muted }]}>
            {subtitle ?? `Available on ${requiredPlan}.`}
          </Text>
        </View>
      </View>
      <Pressable
        onPress={() => router.push('/subscription' as Href)}
        style={[styles.cta, { backgroundColor: colors.accent }]}
        accessibilityRole="button"
        accessibilityLabel={`Upgrade to ${requiredPlan} to unlock ${title}`}
      >
        <Text style={[styles.ctaText, { color: colors.accentText }]}>
          Upgrade to {requiredPlan}
        </Text>
      </Pressable>
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 12,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 10,
  },
  iconWrap: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: { flex: 1 },
  title: { fontSize: 14, fontWeight: '700' },
  subtitle: { fontSize: 12, marginTop: 2 },
  cta: {
    borderRadius: 8,
    paddingVertical: 9,
    alignItems: 'center',
  },
  ctaText: { fontSize: 13, fontWeight: '700' },
});
