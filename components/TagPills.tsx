import React from 'react';
import { View, Text } from 'react-native';

export default function TagPills({ tags }: { tags?: string[] }) {
  if (!tags?.length) return null;
  return (
    <View style={{ flexDirection:'row', flexWrap:'wrap', gap:6, marginTop:6 }}>
      {tags.slice(0,4).map((t) => (
        <View key={t} style={{ paddingHorizontal:8, paddingVertical:4, borderRadius:999, borderWidth:1, borderColor:'#ddd' }}>
          <Text style={{ fontSize:12 }}>{t}</Text>
        </View>
      ))}
    </View>
  );
}
