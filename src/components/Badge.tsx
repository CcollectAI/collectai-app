import { View, Text } from 'react-native';
import { colors, radius } from '../theme/tokens';

export default function Badge({ text, tone='neutral' }:{ text:string; tone?:'neutral'|'pos'|'neg' }) {
  const bg = tone==='pos' ? '#ECFDF5' : tone==='neg' ? '#FEF2F2' : '#F1F5F9';
  const col = tone==='pos' ? colors.positive : tone==='neg' ? colors.negative : colors.subtext;
  return (
    <View style={{ backgroundColor: bg, paddingHorizontal: 10, paddingVertical: 6, borderRadius: radius.xl, borderWidth:1, borderColor: '#E5E7EB' }}>
      <Text style={{ fontWeight:'700', color: col, fontSize:12 }}>{text}</Text>
    </View>
  );
}
