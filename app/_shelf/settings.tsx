import { ScrollView, Text } from 'react-native';
import Card from '@/components/Card';
import { theme } from '@/theme';

export default function Settings() {
  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
      <Card>
        <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>Settings</Text>
        <Text style={{ color: theme.colors.subtext, marginTop: 8 }}>Coming soon.</Text>
      </Card>
    </ScrollView>
  );
}
