/**
 * UpgradePrompt — Inline banner prompting users to upgrade their plan.
 * Shows when a feature requires a higher plan tier.
 */

import React, { useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { router, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useTranslation } from 'react-i18next';
import { recordPaywallEvent, recordFeatureAttempt } from '@/api/intelligenceApi';

type Props = {
  feature: string;
  requiredPlan?: string;
};

export const UpgradePrompt = React.memo(function UpgradePrompt({ feature, requiredPlan = 'Pro' }: Props) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { t } = useTranslation();

  // Demand-side intelligence: render = "user hit a Pro gate AND saw the
  // upgrade prompt", which is BOTH a paywall view AND a feature-gated
  // attempt. Track once on mount; the two signal types let us measure
  // gate hits separately from paywall conversion in /intelligence.
  useEffect(() => {
    recordPaywallEvent({ feature, action: 'viewed' });
    recordFeatureAttempt(feature);
  }, [feature]);

  // 2026-05-22: ditched warningBg (#78350F brown in dark mode looked jarring
  // and mis-categorised — a locked premium feature reads as "premium gate"
  // not "warning"). Use Tiffany Blue tint for on-brand "premium" framing.
  return (
    <View style={[styles.container, { backgroundColor: colors.accent + '15', borderColor: colors.accent + '40' }]}>
      <View style={styles.row}>
        <Ionicons name="lock-closed-outline" size={18} color={colors.accent} />
        <View style={styles.text}>
          <Text style={[styles.title, { color: colors.text }]}>
            {t('billing.feature_requires_plan', { feature, plan: requiredPlan })}
          </Text>
          <Text style={[styles.subtitle, { color: colors.muted }]}>{t('billing.unlock_feature')}</Text>
        </View>
      </View>
      <AnimatedPressable
        // Goes to the PAYWALL, not Settings. This read `/settings` until
        // 2026-08-15: every Pro gate in the app (set completion, analytics,
        // market movers, item detail) dead-ended on the settings screen, so
        // there was no route from hitting a gate to actually subscribing.
        // The `as Href` cast is what let a valid-but-wrong route through.
        onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.push('/subscription' as Href); }}
        style={[styles.btn, { backgroundColor: colors.accent }]}
        accessibilityRole="button"
        accessibilityLabel={t('billing.upgrade_to_plan', { plan: requiredPlan })}
      >
        <Text style={[styles.btnText, { color: colors.accentText }]}>{t('billing.upgrade')}</Text>
      </AnimatedPressable>
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
  text: {
    flex: 1,
  },
  title: {
    fontSize: 14,
    fontWeight: '700',
  },
  subtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  btn: {
    borderRadius: 8,
    paddingVertical: 8,
    alignItems: 'center',
  },
  btnText: {
    fontSize: 13,
    fontWeight: '700',
  },
});
