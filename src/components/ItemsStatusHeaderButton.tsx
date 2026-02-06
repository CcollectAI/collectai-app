import React from 'react';
import { Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';

export const ItemsStatusHeaderButton: React.FC = () => {
  const router = useRouter();
  const { settings } = useSettings();

  return (
    <AnimatedPressable
      onPress={() => {
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
        router.push('/items-status');
      }}
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: 10,
        paddingVertical: 4,
        borderRadius: 999,
        backgroundColor: '#e0f2fe',
      }}
    >
      <View
        style={{
          width: 6,
          height: 6,
          borderRadius: 999,
          backgroundColor: '#0ea5e9',
          marginRight: 6,
        }}
      />
      <Text
        style={{
          fontSize: 11,
          fontWeight: '600',
          color: '#0369a1',
        }}
      >
        Status & leaderboard
      </Text>
    </AnimatedPressable>
  );
};

export default ItemsStatusHeaderButton;
