import { View, Text } from 'react-native';
import { colors, fonts, spacing } from '../theme/tokens';

export default function Header({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <View style={{ paddingHorizontal: spacing(2), paddingTop: spacing(2), paddingBottom: spacing(1) }}>
      <Text style={fonts.h1}>{title}</Text>
      {subtitle ? <Text style={{ ...fonts.small, marginTop: 4 }}>{subtitle}</Text> : null}
    </View>
  );
}
