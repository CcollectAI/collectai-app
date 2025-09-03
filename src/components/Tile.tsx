import { View, ViewProps, Text } from 'react-native';
import { colors, radius, shadow } from '../theme/tokens';

export default function Tile({ value, label, right, style }: {
  value: string; label: string; right?: React.ReactNode; style?: ViewProps['style'];
}) {
  return (
    <View style={[{
      backgroundColor: colors.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border,
      padding: 16, ...shadow.card, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    }, style as any]}>
      <View>
        <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text }}>{value}</Text>
        <Text style={{ fontSize: 13, color: colors.subtext, marginTop: 4 }}>{label}</Text>
      </View>
      {right ?? null}
    </View>
  );
}
