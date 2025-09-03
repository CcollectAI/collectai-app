import React from 'react';
import { View, TextInput } from 'react-native';

export default function SearchBar({ value, onChange }: { value: string; onChange: (t: string) => void }) {
  return (
    <View style={{ padding: 8 }}>
      <TextInput
        value={value}
        onChangeText={onChange}
        placeholder="Search title…"
        style={{ borderWidth:1,borderColor:'#ddd',padding:10,borderRadius:8 }}
      />
    </View>
  );
}
