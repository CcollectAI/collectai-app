import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import type { AppTheme } from '@/hooks/useAppTheme';

type Props = {
  categoryName: string;
  categoryTagline: string;
  following: boolean;
  onToggleFollow: () => void;
  colors: AppTheme['colors'];
};

const CategoryHeaderCard: React.FC<Props> = ({
  categoryName,
  categoryTagline,
  following,
  onToggleFollow,
  colors,
}) => (
  <View style={[styles.headerCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
    <View style={styles.headerContent}>
      <Text style={[styles.categoryName, { color: colors.text }]}>{categoryName}</Text>
      <Text style={[styles.categoryTagline, { color: colors.muted }]} numberOfLines={3}>
        {categoryTagline}
      </Text>
    </View>
    <AnimatedPressable
      style={[
        styles.followButton,
        { borderColor: colors.accent },
        following && { backgroundColor: colors.accent },
      ]}
      onPress={onToggleFollow}
      accessibilityRole="button"
      accessibilityLabel={following ? `Unfollow ${categoryName}` : `Follow ${categoryName}`}
    >
      <Ionicons
        name={following ? 'checkmark' : 'add'}
        size={16}
        color={following ? '#fff' : colors.accent}
      />
      <Text
        style={[
          styles.followButtonText,
          { color: colors.accent },
          following && { color: '#fff' },
        ]}
      >
        {following ? 'Following' : 'Follow'}
      </Text>
    </AnimatedPressable>
  </View>
);

export default React.memo(CategoryHeaderCard);

const styles = StyleSheet.create({
  headerCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 14,
    marginBottom: 16,
  },
  headerContent: {
    marginBottom: 12,
  },
  categoryName: {
    fontSize: 20,
    fontWeight: '700',
  },
  categoryTagline: {
    marginTop: 4,
    fontSize: 13,
    lineHeight: 18,
  },
  followButton: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: 1,
  },
  followButtonText: {
    marginLeft: 4,
    fontSize: 13,
    fontWeight: '600',
  },
});
