import React from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import type { SponsorTier } from '@/data/events';

const TIERS: { id: SponsorTier; name: string; badge?: string; features: string[] }[] = [
  { id: 'featured', name: 'Featured', features: ['Event listing', 'Category placement', 'Basic analytics'] },
  { id: 'promoted', name: 'Promoted', badge: 'POPULAR', features: ['Everything in Featured', 'Homepage banner', 'Push notifications', 'Priority support'] },
  { id: 'spotlight', name: 'Spotlight', features: ['Everything in Promoted', 'Dedicated landing page', 'Custom branding', 'Advanced analytics'] },
];

const SHADOW_MD = Platform.select({
  ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.08, shadowRadius: 8 },
  android: { elevation: 3 },
  default: {},
}) as Record<string, unknown>;

interface Props {
  selectedTier: SponsorTier;
  onSelectTier: (tier: SponsorTier) => void;
  billingMode: 'per_event' | 'monthly';
  onBillingModeChange: (mode: 'per_event' | 'monthly') => void;
  onConfirm: () => void;
  onCancel: () => void;
  hapticsEnabled?: boolean;
}

export const TierPickerPanel = React.memo(function TierPickerPanel({
  selectedTier, onSelectTier, billingMode, onBillingModeChange, onConfirm, onCancel, hapticsEnabled,
}: Props) {
  const { colors } = useAppTheme();

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }, SHADOW_MD]}>
      <View style={styles.header}>
        <View style={[styles.iconCircle, { backgroundColor: colors.accent + '12' }]}>
          <Ionicons name="ribbon-outline" size={16} color={colors.accent} />
        </View>
        <View>
          <Text style={[styles.title, { color: colors.text }]}>Select Sponsorship Tier</Text>
          <Text style={[styles.subtitle, { color: colors.muted }]}>Choose the visibility level for your event</Text>
        </View>
      </View>

      <View style={[styles.divider, { backgroundColor: colors.border }]} />

      {TIERS.map((tier, i) => (
        <AnimatedPressable
          key={tier.id}
          onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled }); onSelectTier(tier.id); }}
          style={[
            styles.tierCard,
            { backgroundColor: selectedTier === tier.id ? colors.accent + '06' : 'transparent', borderColor: selectedTier === tier.id ? colors.accent : colors.border },
            selectedTier === tier.id && { borderWidth: 2 },
            i < TIERS.length - 1 && { marginBottom: 8 },
          ]}
          accessibilityRole="radio"
          accessibilityState={{ selected: selectedTier === tier.id }}
          accessibilityLabel={`${tier.name} tier`}
        >
          <View style={styles.tierRow}>
            <View style={[styles.radioOuter, { borderColor: selectedTier === tier.id ? colors.accent : colors.muted }]}>
              {selectedTier === tier.id && <View style={[styles.radioInner, { backgroundColor: colors.accent }]} />}
            </View>
            <View style={styles.tierInfo}>
              <View style={styles.tierNameRow}>
                <Text style={[styles.tierName, { color: colors.text }]}>{tier.name}</Text>
                {tier.badge && (
                  <View style={[styles.badge, { backgroundColor: colors.accent }]}>
                    <Text style={styles.badgeText}>{tier.badge}</Text>
                  </View>
                )}
              </View>
              {tier.features.map((f) => (
                <View key={f} style={styles.featureRow}>
                  <Ionicons name="checkmark" size={13} color={colors.accent} />
                  <Text style={[styles.featureText, { color: colors.muted }]}>{f}</Text>
                </View>
              ))}
            </View>
          </View>
        </AnimatedPressable>
      ))}

      <View style={styles.billingRow}>
        <AnimatedPressable
          onPress={() => onBillingModeChange('per_event')}
          style={[styles.billingBtn, { backgroundColor: billingMode === 'per_event' ? colors.accent : colors.background, borderColor: billingMode === 'per_event' ? colors.accent : colors.border }]}
          accessibilityRole="radio"
          accessibilityState={{ selected: billingMode === 'per_event' }}
        >
          <Text style={{ fontSize: 13, fontWeight: '600', color: billingMode === 'per_event' ? '#FFF' : colors.text }}>Per Event</Text>
        </AnimatedPressable>
        <AnimatedPressable
          onPress={() => onBillingModeChange('monthly')}
          style={[styles.billingBtn, { backgroundColor: billingMode === 'monthly' ? colors.accent : colors.background, borderColor: billingMode === 'monthly' ? colors.accent : colors.border }]}
          accessibilityRole="radio"
          accessibilityState={{ selected: billingMode === 'monthly' }}
        >
          <Text style={{ fontSize: 13, fontWeight: '600', color: billingMode === 'monthly' ? '#FFF' : colors.text }}>Monthly</Text>
        </AnimatedPressable>
      </View>

      <View style={[styles.divider, { backgroundColor: colors.border }]} />

      <View style={styles.footer}>
        <AnimatedPressable onPress={onCancel} style={[styles.outlineBtn, { borderColor: colors.border }]} accessibilityRole="button" accessibilityLabel="Cancel">
          <Text style={[styles.outlineBtnText, { color: colors.muted }]}>Cancel</Text>
        </AnimatedPressable>
        <AnimatedPressable onPress={onConfirm} style={[styles.primaryBtn, { backgroundColor: colors.accent }]} accessibilityRole="button" accessibilityLabel="Continue">
          <Text style={styles.primaryBtnText}>{billingMode === 'monthly' ? 'Subscribe' : 'Continue'}</Text>
          <Ionicons name="arrow-forward" size={15} color="#FFFFFF" />
        </AnimatedPressable>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  container: { borderRadius: 14, borderWidth: 1, padding: 16, marginBottom: 24 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  iconCircle: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 15, fontWeight: '700', letterSpacing: -0.2 },
  subtitle: { fontSize: 12, marginTop: 1 },
  divider: { height: 1, marginVertical: 14 },
  tierCard: { borderRadius: 12, borderWidth: 1, padding: 14 },
  tierRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  radioOuter: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, alignItems: 'center', justifyContent: 'center', marginTop: 1 },
  radioInner: { width: 10, height: 10, borderRadius: 5 },
  tierInfo: { flex: 1 },
  tierNameRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  tierName: { fontSize: 14, fontWeight: '700' },
  badge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 5 },
  badgeText: { fontSize: 9, fontWeight: '800', color: '#FFFFFF', letterSpacing: 0.5 },
  featureRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 2 },
  featureText: { fontSize: 12, flex: 1 },
  billingRow: { flexDirection: 'row', gap: 8, marginTop: 12 },
  billingBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, borderWidth: 1, alignItems: 'center' },
  footer: { flexDirection: 'row', gap: 10 },
  primaryBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 11, paddingHorizontal: 18, borderRadius: 10 },
  primaryBtnText: { fontSize: 13, fontWeight: '600', color: '#FFFFFF' },
  outlineBtn: { alignItems: 'center', justifyContent: 'center', paddingVertical: 11, paddingHorizontal: 18, borderRadius: 10, borderWidth: 1 },
  outlineBtnText: { fontSize: 13, fontWeight: '600' },
});
