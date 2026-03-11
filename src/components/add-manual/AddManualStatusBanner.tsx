/**
 * AddManualStatusBanner — Status banner for saving/success/error states.
 */

import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';

type BannerType = 'info' | 'success' | 'error';

interface AddManualStatusBannerProps {
  type: BannerType;
  text: string;
  isSaving: boolean;
}

function getBannerColors(type: BannerType, accentColor: string) {
  if (type === 'error') return { bg: '#FEF2F2', border: '#EF4444', icon: 'warning-outline' as const, iconColor: '#EF4444' };
  if (type === 'success') return { bg: accentColor + '15', border: accentColor, icon: 'checkmark-circle-outline' as const, iconColor: accentColor };
  return { bg: '#FEF3C7', border: '#F59E0B', icon: 'time-outline' as const, iconColor: '#F59E0B' };
}

export const AddManualStatusBanner = React.memo(function AddManualStatusBanner({
  type,
  text,
  isSaving,
}: AddManualStatusBannerProps) {
  const { colors } = useAppTheme();
  const bannerColors = getBannerColors(type, colors.accent);

  return (
    <View style={[styles.banner, { backgroundColor: bannerColors.bg, borderColor: bannerColors.border }]}>
      <View style={styles.bannerIconBox}>
        {isSaving ? (
          <ActivityIndicator size="small" color={colors.accent} />
        ) : (
          <Ionicons name={bannerColors.icon} size={18} color={bannerColors.iconColor} />
        )}
      </View>
      <Text style={[styles.bannerText, { color: colors.text }]}>{text}</Text>
    </View>
  );
});

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row', alignItems: 'center', borderRadius: 10, borderWidth: 1,
    paddingHorizontal: 12, paddingVertical: 10, marginBottom: 16,
  },
  bannerIconBox: { width: 24, height: 24, alignItems: 'center', justifyContent: 'center', marginRight: 10 },
  bannerText: { fontSize: 13, flex: 1, fontWeight: '500' },
});
