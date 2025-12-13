import { View, Pressable, Text } from 'react-native';
import { theme } from '@/theme';

type Props = { options: string[]; value: string; onChange: (v: string) => void; };
export default function RangeToggle({ options, value, onChange }: Props) {
  return (
    <View style={{ flexDirection: 'row', gap: theme.spacing.lg, justifyContent: 'flex-end' }}>
      {options.map((opt) => {
        const active = opt === value;
        return (
          <Pressable key={opt} onPress={() => onChange(opt)} style={{ paddingVertical: theme.spacing.xs }}>
            <Text style={{ fontWeight: active ? '700' : '500', color: active ? theme.colors.navy : theme.colors.subtext }}>{opt}</Text>
            <View style={{ height: 2, marginTop: 4, backgroundColor: active ? theme.colors.navy : 'transparent' }} />
          </Pressable>
        );
      })}
    </View>
  );
}
