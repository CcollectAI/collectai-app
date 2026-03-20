/**
 * Bottom action bar for the Items screen with export CSV and projects buttons.
 *
 * Extracted from app/(tabs)/items.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { BETA_MODE } from '@/config/featureFlags';

interface ItemsBottomActionBarProps {
  exporting: boolean;
  exportStatus: string | null;
  isLoadingMore: boolean;
  onExportCSV: () => void;
  onOpenProjects: () => void;
}

export const ItemsBottomActionBar = React.memo(function ItemsBottomActionBar({
  exporting,
  exportStatus,
  isLoadingMore,
  onExportCSV,
  onOpenProjects,
}: ItemsBottomActionBarProps) {
  const { colors } = useAppTheme();

  return (
    <>
      <View style={[styles.bottomActionBar, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <Text style={[styles.bottomActionTitle, { color: colors.text }]}>
          Actions
        </Text>

        <View style={styles.bottomActionButtons}>
          <AnimatedPressable
            style={[
              styles.actionButtonPrimary,
              { backgroundColor: colors.accent },
              exporting && styles.actionButtonDisabled,
            ]}
            onPress={onExportCSV}
            disabled={exporting}
            accessibilityRole="button"
            accessibilityLabel="Download collection overview as CSV"
          >
            {exporting ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <Ionicons name="download-outline" size={18} color="#FFFFFF" />
            )}
            <Text style={styles.actionButtonPrimaryText}>
              {exporting ? 'Exporting...' : 'Download overview'}
            </Text>
          </AnimatedPressable>

          {!BETA_MODE && (
            <AnimatedPressable
              style={[
                styles.actionButtonSecondary,
                { borderColor: colors.accent },
              ]}
              onPress={onOpenProjects}
              accessibilityRole="button"
              accessibilityLabel="Open build and paint projects"
            >
              <Ionicons name="color-palette-outline" size={18} color={colors.accent} />
              <Text style={[styles.actionButtonSecondaryText, { color: colors.accent }]}>
                Projects
              </Text>
            </AnimatedPressable>
          )}
        </View>

        {exportStatus && (
          <View style={[styles.exportStatusBanner, { backgroundColor: colors.accent + '15' }]}>
            <Ionicons name="checkmark-circle" size={16} color={colors.accent} />
            <Text style={[styles.exportStatusText, { color: colors.accent }]}>
              {exportStatus}
            </Text>
          </View>
        )}
      </View>

      {isLoadingMore && (
        <View style={styles.loadingMoreContainer}>
          <ActivityIndicator size="small" color={colors.accent} />
        </View>
      )}
    </>
  );
});

const styles = StyleSheet.create({
  bottomActionBar: {
    marginTop: 16,
    marginBottom: 24,
    padding: 16,
    borderRadius: 16,
    borderWidth: 1,
  },
  bottomActionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 14,
  },
  bottomActionButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  actionButtonPrimary: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 12,
    gap: 8,
  },
  actionButtonPrimaryText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  actionButtonSecondary: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 12,
    borderWidth: 1.5,
    gap: 8,
    backgroundColor: 'transparent',
  },
  actionButtonSecondaryText: {
    fontSize: 14,
    fontWeight: '600',
  },
  actionButtonDisabled: {
    opacity: 0.6,
  },
  exportStatusBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: 12,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 10,
  },
  exportStatusText: {
    fontSize: 13,
    fontWeight: '500',
  },
  loadingMoreContainer: {
    paddingVertical: 16,
    alignItems: 'center',
  },
});
