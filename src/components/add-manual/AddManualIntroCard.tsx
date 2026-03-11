/**
 * AddManualIntroCard — Header card explaining manual entry mode.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';

export const AddManualIntroCard = React.memo(function AddManualIntroCard() {
  const { colors } = useAppTheme();

  return (
    <View style={[styles.introCard, { backgroundColor: colors.accent + '10', borderColor: colors.accent + '30' }]}>
      <View style={[styles.introIconWrap, { backgroundColor: colors.accent + '20' }]}>
        <Ionicons name="create-outline" size={20} color={colors.accent} />
      </View>
      <View style={styles.introText}>
        <Text style={[styles.introTitle, { color: colors.text }]}>Manual Entry</Text>
        <Text style={[styles.introSubtitle, { color: colors.muted }]}>
          Enter item details yourself for full control
        </Text>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  introCard: {
    flexDirection: 'row', alignItems: 'center', padding: 14, borderRadius: 12, borderWidth: 1, marginBottom: 20,
  },
  introIconWrap: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  introText: { flex: 1 },
  introTitle: { fontSize: 15, fontWeight: '600', marginBottom: 2 },
  introSubtitle: { fontSize: 13 },
});
