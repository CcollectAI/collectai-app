/**
 * EventHostSection — Displays the host collector profile card.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { PublicUserProfileCard } from '@/components/PublicUserProfileCard';
import type { PublicUserProfile } from '@/data';

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
  const { colors } = useAppTheme();

  if (!profile && !loading) return null;

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>
        Host collector
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
