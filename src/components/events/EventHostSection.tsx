/**
 * EventHostSection — Displays the host collector profile card.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { PublicUserProfileCard } from '@/components/PublicUserProfileCard';
import type { PublicUserProfile } from '@/data';
import { useTranslation } from 'react-i18next';

interface EventHostSectionProps {
  profile: PublicUserProfile | null;
  loading: boolean;
  onPress?: () => void;
}

export const EventHostSection = React.memo(function EventHostSection({
  profile,
  loading,
  onPress,
}: EventHostSectionProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  if (!profile && !loading) return null;

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>
        {t('common.host_collector', { defaultValue: 'Host collector' })}
      </Text>
      <PublicUserProfileCard
        profile={profile}
        loading={loading}
        onPress={onPress}
      />
    </View>
  );
});

const styles = StyleSheet.create({
  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 8,
  },
});
