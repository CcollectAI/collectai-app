import { View, Pressable, Text } from 'react-native';
import { theme } from '@/theme';

type Props = { segments: string[]; value: string; onChange: (v: string) => void; };
export default function Segmented({ segments, value, onChange }: Props) {
  return (
    <View style={{ flexDirection: 'row', borderWidth: 1, borderColor: theme.colors.border }}>
      {segments.map((s) => {
        const active = s === value;
        return (
          <Pressable
            key={s}
            onPress={() => onChange(s)}
            style={{
              flex: 1,
              paddingVertical: theme.spacing.sm,
              alignItems: 'center',
              backgroundColor: active ? theme.colors.card : 'transparent',
            }}
          >
            <Text style={{ color: active ? theme.colors.navy : theme.colors.subtext, fontWeight: active ? '700' : '500' }}>
              {s}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
