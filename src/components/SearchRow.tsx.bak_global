import { View, Text, Image } from 'react-native';
import Icon from '@/components/Icon';
import { theme } from '@/theme';
export default function SearchRow({ title, subtitle, price, badge, thumbUri }:{
  title:string; subtitle:string; price:string; badge?:string; thumbUri?:string|null;
}) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 12, borderBottomWidth: 1, borderColor: theme.colors.border }}>
      <View style={{ width: 56, height: 56, borderWidth: 1, borderColor: theme.colors.border, justifyContent: 'center', alignItems: 'center', marginRight: 12 }}>
        {thumbUri ? <Image source={{ uri: thumbUri }} style={{ width: 54, height: 54 }} /> : <Icon name="image-outline" />}
      </View>
      <View style={{ flex: 1, paddingRight: 12 }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '600' }} numberOfLines={1}>{title}</Text>
        <Text style={{ color: theme.colors.subtext, fontSize: 12 }} numberOfLines={1}>{subtitle}</Text>
        {badge ? <Text style={{ color: theme.colors.subtext, fontSize: 10, marginTop: 2 }}>{badge}</Text> : null}
      </View>
      <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{price}</Text>
    </View>
  );
}
