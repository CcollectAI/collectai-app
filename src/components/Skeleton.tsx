/**
 * Skeleton loading components for placeholder UI while data loads.
 * Provides shimmer effect for visual feedback.
 */

import React, { useEffect, useRef } from 'react';
import { View, StyleSheet, Animated, ViewStyle } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';

interface SkeletonProps {
  width?: number | string;
  height?: number;
  borderRadius?: number;
  style?: ViewStyle;
}

export function Skeleton({
  width = '100%',
  height = 16,
  borderRadius = 4,
  style,
}: SkeletonProps) {
  const { colors } = useAppTheme();
  const shimmerAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(shimmerAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        }),
        Animated.timing(shimmerAnim, {
          toValue: 0,
          duration: 1000,
          useNativeDriver: true,
        }),
      ])
    );
    animation.start();
    return () => animation.stop();
  }, [shimmerAnim]);

  const opacity = shimmerAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0.3, 0.7],
  });

  return (
    <Animated.View
      accessibilityRole="none"
      accessibilityLabel="Loading"
      style={[
        styles.skeleton,
        {
          backgroundColor: colors.skeleton,
          width: width as number | `${number}%`,
          height,
          borderRadius,
          opacity,
        },
        style,
      ]}
    />
  );
}

// Pre-built skeleton patterns for common UI elements

export function SkeletonItemCard() {
  return (
    <View style={styles.itemCard}>
      <Skeleton width={80} height={80} borderRadius={12} />
      <View style={styles.itemCardContent}>
        <Skeleton width="70%" height={16} borderRadius={4} />
        <Skeleton width="40%" height={12} borderRadius={4} style={{ marginTop: 8 }} />
        <Skeleton width="30%" height={14} borderRadius={4} style={{ marginTop: 8 }} />
      </View>
    </View>
  );
}

export function SkeletonItemRow() {
  return (
    <View style={styles.itemRow}>
      <Skeleton width={56} height={56} borderRadius={10} />
      <View style={styles.itemRowContent}>
        <Skeleton width="60%" height={14} borderRadius={4} />
        <Skeleton width="35%" height={12} borderRadius={4} style={{ marginTop: 6 }} />
      </View>
      <Skeleton width={60} height={16} borderRadius={4} />
    </View>
  );
}

export function SkeletonEventCard() {
  return (
    <View style={styles.eventCard}>
      <View style={styles.eventHeader}>
        <Skeleton width={40} height={40} borderRadius={8} />
        <View style={{ flex: 1, marginLeft: 12 }}>
          <Skeleton width="80%" height={14} borderRadius={4} />
          <Skeleton width="50%" height={12} borderRadius={4} style={{ marginTop: 6 }} />
        </View>
      </View>
      <Skeleton width="100%" height={12} borderRadius={4} style={{ marginTop: 12 }} />
      <Skeleton width="70%" height={12} borderRadius={4} style={{ marginTop: 6 }} />
    </View>
  );
}

export function SkeletonPortfolioHeader() {
  return (
    <View style={styles.portfolioHeader}>
      <Skeleton width={120} height={32} borderRadius={6} />
      <Skeleton width={80} height={16} borderRadius={4} style={{ marginTop: 8 }} />
      <View style={styles.portfolioChart}>
        <Skeleton width="100%" height={150} borderRadius={12} />
      </View>
    </View>
  );
}

export function SkeletonCategoryPills() {
  return (
    <View style={styles.categoryPills}>
      <Skeleton width={80} height={28} borderRadius={14} />
      <Skeleton width={100} height={28} borderRadius={14} />
      <Skeleton width={70} height={28} borderRadius={14} />
      <Skeleton width={90} height={28} borderRadius={14} />
    </View>
  );
}

export function SkeletonAnalytics() {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.analyticsCard, { backgroundColor: colors.card }]}>
      <Skeleton width="50%" height={24} borderRadius={6} />
      <Skeleton width="100%" height={120} borderRadius={12} style={{ marginTop: 16 }} />
      <View style={styles.analyticsRow}>
        <Skeleton width="30%" height={14} borderRadius={4} />
        <Skeleton width="30%" height={14} borderRadius={4} />
        <Skeleton width="30%" height={14} borderRadius={4} />
      </View>
      <Skeleton width="80%" height={12} borderRadius={4} style={{ marginTop: 12 }} />
    </View>
  );
}

export function SkeletonDeal() {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.dealCard, { backgroundColor: colors.card }]}>
      <View style={styles.dealHeader}>
        <Skeleton width={48} height={48} borderRadius={8} />
        <View style={{ flex: 1, marginLeft: 12 }}>
          <Skeleton width="70%" height={16} borderRadius={4} />
          <Skeleton width="40%" height={12} borderRadius={4} style={{ marginTop: 6 }} />
        </View>
        <Skeleton width={60} height={24} borderRadius={12} />
      </View>
      <View style={styles.dealDetails}>
        <Skeleton width="50%" height={12} borderRadius={4} />
        <Skeleton width="35%" height={12} borderRadius={4} style={{ marginTop: 6 }} />
      </View>
    </View>
  );
}

export function SkeletonChat() {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.chatContainer, { backgroundColor: colors.background }]}>
      {[0.6, 0.4, 0.7, 0.5, 0.3].map((w, i) => (
        <View
          key={i}
          style={[
            styles.chatBubble,
            i % 2 === 0 ? styles.chatBubbleLeft : styles.chatBubbleRight,
            { backgroundColor: colors.card },
          ]}
        >
          <Skeleton width={`${w * 100}%`} height={14} borderRadius={4} />
          {w > 0.5 && <Skeleton width="40%" height={12} borderRadius={4} style={{ marginTop: 6 }} />}
        </View>
      ))}
    </View>
  );
}

export function SkeletonList({ count = 5, type = 'row' }: { count?: number; type?: 'row' | 'card' | 'event' | 'deal' | 'analytics' }) {
  const Component =
    type === 'card' ? SkeletonItemCard :
    type === 'event' ? SkeletonEventCard :
    type === 'deal' ? SkeletonDeal :
    type === 'analytics' ? SkeletonAnalytics :
    SkeletonItemRow;
  return (
    <View style={styles.list}>
      {Array.from({ length: count }).map((_, i) => (
        <Component key={i} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  skeleton: {
    // backgroundColor now set dynamically via theme
  },
  itemCard: {
    flexDirection: 'row',
    padding: 12,
    marginBottom: 12,
    borderRadius: 12,
  },
  itemCardContent: {
    flex: 1,
    marginLeft: 12,
    justifyContent: 'center',
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    marginBottom: 8,
  },
  itemRowContent: {
    flex: 1,
    marginLeft: 12,
  },
  eventCard: {
    padding: 14,
    marginBottom: 12,
    borderRadius: 12,
  },
  eventHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  portfolioHeader: {
    padding: 16,
    alignItems: 'center',
  },
  portfolioChart: {
    width: '100%',
    marginTop: 16,
  },
  categoryPills: {
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 16,
    marginBottom: 12,
  },
  list: {
    paddingHorizontal: 16,
  },
  analyticsCard: {
    padding: 16,
    marginBottom: 12,
    borderRadius: 12,
  },
  analyticsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 12,
  },
  dealCard: {
    padding: 14,
    marginBottom: 12,
    borderRadius: 12,
  },
  dealHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  dealDetails: {
    marginTop: 12,
  },
  chatContainer: {
    padding: 16,
  },
  chatBubble: {
    padding: 12,
    borderRadius: 16,
    marginBottom: 8,
    maxWidth: '75%',
  },
  chatBubbleLeft: {
    alignSelf: 'flex-start',
    borderBottomLeftRadius: 4,
  },
  chatBubbleRight: {
    alignSelf: 'flex-end',
    borderBottomRightRadius: 4,
  },
});

export default Skeleton;
