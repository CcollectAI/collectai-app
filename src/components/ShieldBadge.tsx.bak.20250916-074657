import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/theme';

export type Tier = 'silver' | 'gold' | 'platinum';
const COLORS: Record<Tier, string> = { silver: '#C0C0C0', gold: '#D4AF37', platinum: '#B0BEC5' };

export default function ShieldBadge({ tier }: { tier: Tier }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#fff', borderWidth: 1, borderColor: COLORS[tier], paddingVertical: 2, paddingHorizontal: 6 }}>
      <Ionicons name="shield-outline" size={14} color={theme.colors.navy} />
      <Text style={{ color: theme.colors.navy, fontWeight: '700', fontSize: 12, marginLeft: 4 }}>
        {tier[0].toUpperCase() + tier.slice(1)}
      </Text>
    </View>
  );
}
