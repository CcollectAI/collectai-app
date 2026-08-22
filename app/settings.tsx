/**
 * Settings screen route.
 */
import React from 'react';
import { View, StyleSheet } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import Settings from '@/screens/Settings';
import { QuickNavBar } from '@/components/QuickNavBar';

export default function SettingsScreenWithBoundary() {
  // `?editProfile=1` opens the profile editor on arrival.
  //
  // Read HERE rather than deeper: check-route-param-handoff resolves a push
  // target to its ROUTE FILE, so a param consumed only by src/screens/Settings
  // would report "that route reads: (none)" and the contract would stop being
  // checkable. It is also why the push must target `/settings` and not a
  // component.
  const { editProfile } = useLocalSearchParams<{ editProfile?: string }>();
  return (
    <ScreenErrorBoundary screenName="Settings">
      <View style={settingsStyles.container}>
        <Settings openProfileEditor={editProfile === '1'} />
        <QuickNavBar />
      </View>
    </ScreenErrorBoundary>
  );
}

const settingsStyles = StyleSheet.create({
  container: { flex: 1 },
});
