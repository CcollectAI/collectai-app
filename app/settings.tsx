/**
 * Settings screen route.
 */
import React from 'react';
import { View, StyleSheet } from 'react-native';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import Settings from '@/screens/Settings';

export default function SettingsScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Settings">
      <View style={settingsStyles.container}>
        <Settings />
      </View>
    </ScreenErrorBoundary>
  );
}

const settingsStyles = StyleSheet.create({
  container: { flex: 1 },
});
