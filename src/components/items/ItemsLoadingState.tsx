/**
 * ItemsLoadingState — Skeleton placeholder shown while items are loading.
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAppTheme } from '@/hooks/useAppTheme';
import { SkeletonList, SkeletonCategoryPills, SkeletonGalleryGrid } from '@/components/Skeleton';

interface ItemsLoadingStateProps {
  viewMode: 'list' | 'gallery';
}

export const ItemsLoadingState = React.memo(function ItemsLoadingState({
  viewMode,
}: ItemsLoadingStateProps) {
  const { colors } = useAppTheme();

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <View style={styles.skeletonContainer}>
        <View style={styles.skeletonHeader}>
          <View style={{ width: 100, height: 24, backgroundColor: colors.skeleton, borderRadius: 6 }} />
          <View style={{ width: 150, height: 16, backgroundColor: colors.skeleton, borderRadius: 4, marginTop: 8 }} />
        </View>
        <View style={styles.skeletonSearch}>
          <View style={{ width: '100%', height: 44, backgroundColor: colors.skeleton, borderRadius: 10 }} />
        </View>
        <SkeletonCategoryPills />
        {viewMode === 'gallery' ? (
          <SkeletonGalleryGrid count={6} />
        ) : (
          <SkeletonList count={6} type="row" />
        )}
      </View>
    </SafeAreaView>
  );
});

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  skeletonContainer: {
    flex: 1,
    paddingHorizontal: 16,
    paddingTop: 12,
  },
  skeletonHeader: {
    marginBottom: 16,
  },
  skeletonSearch: {
    marginBottom: 16,
  },
});
