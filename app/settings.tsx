/**
 * Settings screen route.
 */
import React from 'react';
import { View, StyleSheet } from 'react-native';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import Settings from '@/screens/Settings';
import { QuickNavBar } from '@/components/QuickNavBar';

export default function SettingsScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Settings">
      <View style={settingsStyles.container}>
        <Settings />
        <QuickNavBar />
      </View>
    </ScreenErrorBoundary>
  );
}

const settingsStyles = StyleSheet.create({
  container: { flex: 1 },
});
