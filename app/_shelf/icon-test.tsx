import { View, Text, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function IconTest() {
  const names = [
    'settings-outline','share-outline','stats-chart-outline','albums-outline',
    'add-circle-outline','cart-outline','chevron-down','close','checkmark',
    'image-outline','search-outline','shield-outline'
  ];
  return (
    <ScrollView contentContainerStyle={{ padding: 24, gap: 16 }}>
      <Text style={{ fontWeight: '800', fontSize: 18 }}>Ionicons Sanity Check</Text>
      <Text style={{ color: '#64748B' }}>If you don't see icons, you should still see this text.</Text>
      {names.map(n => (
        <View key={n} style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <Ionicons name={n as any} size={22} color="#0B3D91" />
          <Text>{n}</Text>
        </View>
      ))}
    </ScrollView>
  );
}
