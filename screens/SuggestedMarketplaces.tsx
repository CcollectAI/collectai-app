import React from 'react';
import { View, Text } from 'react-native';
import { Category } from '../types/category';
import { CategoryMarketplaces } from '../lib/marketplaces';

export default function SuggestedMarketplaces({ category }: { category: Category }) {
  const suggestions = CategoryMarketplaces[category] ?? [];
  return (
    <View style={{ padding: 12 }}>
      <Text style={{ fontWeight: '700', marginBottom: 8 }}>Suggested Marketplaces</Text>
      {suggestions.map((m) => <Text key={m} style={{ marginBottom: 4 }}>• {m}</Text>)}
    </View>
  );
}
