/**
 * SponsorQuickActions — Quick action bar: New Campaign, Edit Profile, Announce.
 */

import React from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

const SHADOW_SM = Platform.select({
  ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, shadowRadius: 3 },
  android: { elevation: 1 },
  default: {},
}) as Record<string, unknown>;

interface SponsorQuickActionsProps {
  onCreateEvent: () => void;
  onEditProfile: () => void;
  onAnnounce: () => void;
}

export const SponsorQuickActions = React.memo(function SponsorQuickActions({
  onCreateEvent,
  onEditProfile,
  onAnnounce,
}: SponsorQuickActionsProps) {
  const { colors } = useAppTheme();

  return (
    <View style={[styles.actionsBar, { backgroundColor: colors.card, borderColor: colors.border }, SHADOW_SM]}>
      <AnimatedPressable onPress={onCreateEvent} style={[styles.actionBtn, { backgroundColor: colors.accent }]} accessibilityRole="button" accessibilityLabel="New campaign">
        <Ionicons name="add" size={15} color="#FFFFFF" />
        <Text style={styles.actionBtnPrimaryText}>New Campaign</Text>
      </AnimatedPressable>
      <AnimatedPressable onPress={onEditProfile} style={[styles.actionBtn, styles.actionBtnOutline, { borderColor: colors.border }]} accessibilityRole="button" accessibilityLabel="Edit profile">
        <Ionicons name="create-outline" size={14} color={colors.text} />
        <Text style={[styles.actionBtnSecondaryText, { color: colors.text }]}>Edit Profile</Text>
      </AnimatedPressable>
      <AnimatedPressable onPress={onAnnounce} style={[styles.actionBtn, styles.actionBtnOutline, { borderColor: colors.border }]} accessibilityRole="button" accessibilityLabel="Send announcement">
        <Ionicons name="megaphone-outline" size={14} color={colors.text} />
        <Text style={[styles.actionBtnSecondaryText, { color: colors.text }]}>Announce</Text>
      </AnimatedPressable>
    </View>
  );
});

const styles = StyleSheet.create({
  actionsBar: { flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 12, borderWidth: 1, padding: 8, marginBottom: 24 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 8, paddingHorizontal: 12, borderRadius: 8 },
  actionBtnOutline: { borderWidth: 1, backgroundColor: 'transparent' },
  actionBtnPrimaryText: { fontSize: 12, fontWeight: '600', color: '#FFFFFF' },
  actionBtnSecondaryText: { fontSize: 12, fontWeight: '600' },
});
