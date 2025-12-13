import React from 'react';
import { View, Text } from 'react-native';
import { theme } from '@/theme';

export default function TopBar({ right }: { right?: React.ReactNode }) {
  return (
    <View style={{
      backgroundColor:'#fff',
      borderBottomWidth:1, borderColor: theme.colors.border,
      paddingVertical:10, paddingHorizontal:16,
      alignItems:'center', justifyContent:'center'
    }}>
      <Text style={{ color: theme.colors.navy, fontWeight:'800' }}>CollectAI</Text>
      {right ? <View style={{ position:'absolute', right:16, top:10 }}>{right}</View> : null}
    </View>
  );
}
