/**
 * CategoryHeaderCard — tiffany gradient banner per the redesign mockup
 * (web/category-redesign-preview.html `.cathead`: linear-gradient(135deg,
 * #81D8D0 → #2C7873), white text). Follow pill inverts on the gradient:
 * outline-white when idle, solid-white with deep-tiffany text when following.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { AnimatedPressable } from '@/motion';
import { colors as tokens } from '@/theme/tokens';
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
}) => (
  <LinearGradient
    colors={[tokens.brand.base, tokens.brand.deep]}
    start={{ x: 0, y: 0 }}
    end={{ x: 1, y: 1 }}
    style={styles.headerCard}
  >
    <View style={styles.headerContent}>
      <Text style={styles.categoryName}>{categoryName}</Text>
      <Text style={styles.categoryTagline} numberOfLines={3}>
        {categoryTagline}
      </Text>
    </View>
    <AnimatedPressable
      style={[styles.followButton, following && styles.followButtonActive]}
      onPress={onToggleFollow}
      accessibilityRole="button"
      accessibilityLabel={following ? `Unfollow ${categoryName}` : `Follow ${categoryName}`}
    >
      <Ionicons
        name={following ? 'checkmark' : 'add'}
        size={16}
        color={following ? tokens.brand.deep : '#fff'}
      />
      <Text style={[styles.followButtonText, following && styles.followButtonTextActive]}>
        {following ? 'Following' : 'Follow'}
      </Text>
    </AnimatedPressable>
  </LinearGradient>
);

export default React.memo(CategoryHeaderCard);

const styles = StyleSheet.create({
  headerCard: {
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  headerContent: {
    marginBottom: 12,
  },
  categoryName: {
    fontSize: 20,
    fontWeight: '900',
    color: '#fff',
  },
  categoryTagline: {
    marginTop: 4,
    fontSize: 13,
    lineHeight: 18,
    color: '#fff',
    opacity: 0.9,
  },
  followButton: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: '#fff',
  },
  followButtonActive: {
    backgroundColor: '#fff',
    borderColor: '#fff',
  },
  followButtonText: {
    marginLeft: 4,
    fontSize: 13,
    fontWeight: '600',
    color: '#fff',
  },
  followButtonTextActive: {
    color: tokens.brand.deep,
  },
});
