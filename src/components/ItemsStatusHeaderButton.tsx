import React from 'react';
import { TouchableOpacity, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

export const ItemsStatusHeaderButton: React.FC = () => {
  const router = useRouter();

  return (
    <TouchableOpacity
      onPress={() => router.push('/items-status')}
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
    </TouchableOpacity>
  );
};

export default ItemsStatusHeaderButton;
