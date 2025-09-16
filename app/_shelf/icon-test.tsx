import { View, Text, ScrollView } from 'react-native';
import Icon from '@/components/Icon';
export default function IconTest() {
  const names: Parameters<typeof Icon>[0]['name'][] = [
    'settings-outline','share-outline','stats-chart-outline','albums-outline',
    'add-circle-outline','cart-outline','chevron-down','close','checkmark',
    'image-outline','search-outline','shield-outline'
  ];
  return (
    <ScrollView contentContainerStyle={{ padding: 24, gap: 16 }}>
      <Text style={{ fontWeight: '800', fontSize: 18 }}>SVG Icons Sanity Check</Text>
      <Text style={{ color: '#64748B' }}>No fonts used. If you see icons below, we’re done.</Text>
      {names.map(n => (
        <View key={n} style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <Icon name={n} />
          <Text>{n}</Text>
        </View>
      ))}
    </ScrollView>
  );
}
