/**
 * UpgradePrompt — Inline banner prompting users to upgrade their plan.
 * Shows when a feature requires a higher plan tier.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { router, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';

type Props = {
  feature: string;
  requiredPlan?: string;
};

export const UpgradePrompt = React.memo(function UpgradePrompt({ feature, requiredPlan = 'Pro' }: Props) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  return (
    <View style={[styles.container, { backgroundColor: colors.warningBg, borderColor: colors.warning + '40' }]}>
      <View style={styles.row}>
        <Ionicons name="lock-closed-outline" size={18} color={colors.warning} />
        <View style={styles.text}>
          <Text style={[styles.title, { color: colors.text }]}>{feature} requires {requiredPlan}</Text>
          <Text style={[styles.subtitle, { color: colors.muted }]}>Upgrade to unlock this feature</Text>
        </View>
      </View>
      <AnimatedPressable
        onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.push('/settings' as Href); }}
        style={[styles.btn, { backgroundColor: colors.accent }]}
        accessibilityRole="button"
        accessibilityLabel={`Upgrade to ${requiredPlan}`}
      >
        <Text style={[styles.btnText, { color: colors.accentText }]}>Upgrade</Text>
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
