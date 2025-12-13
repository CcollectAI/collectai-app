import React from 'react';
import { View, Text, ScrollView } from 'react-native';
import { useAppTheme } from '@/theme';

export default function TwitchScreen() {
  const theme = useAppTheme();
  const colors = (theme as any)?.colors ?? (theme as any);

  return (
    <ScrollView
      contentContainerStyle={{
        padding: 16,
        backgroundColor: colors?.tiffany ?? colors?.background ?? '#e7fbff',
        flexGrow: 1,
      }}
    >
      <View
        style={{
          backgroundColor: colors?.card ?? '#fff',
          padding: 16,
          borderRadius: 0,
        }}
      >
        <Text style={{ fontSize: 18, fontWeight: '700', color: colors?.navy ?? '#0b1f3a' }}>
          Twitch Overview (Mock)
        </Text>
        <Text style={{ marginTop: 8, fontSize: 14, color: colors?.navy ?? '#0b1f3a' }}>
          Next: show your Twitch handle, live status, follower count, and recent clips.
          We’ll wire real data later.
        </Text>
      </View>
    </ScrollView>
  );
}
