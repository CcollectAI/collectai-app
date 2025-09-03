import { View, Text, Image } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { colors, radius, shadow } from '../theme/tokens';

export default function ItemCard({ title, category, image_url, price, meta }:{
  title:string; category:string; image_url?:string|null; price?:number|null;
  meta?: string | null;   // e.g. "Mint • 2021 • Series 1"
}){
  return (
    <View style={[{ borderRadius:radius.lg, overflow:'hidden', borderWidth:1, borderColor:colors.border, backgroundColor:'#fff', ...shadow.card }]}>
      <View style={{ height:150, backgroundColor:'#F1F5F9' }}>
        {image_url
          ? <Image source={{ uri:image_url }} style={{ width:'100%', height:'100%' }} resizeMode="cover" />
          : <View style={{ flex:1 }} />
        }
        <LinearGradient
          colors={['#00000020','transparent']}
          style={{ position:'absolute', left:0, right:0, top:0, height:60 }}
        />
      </View>
      <View style={{ padding:12, gap:6 }}>
        <Text numberOfLines={1} style={{ fontWeight:'800', fontSize:16, color:colors.text }}>{title}</Text>
        <Text style={{ fontSize:12, color:colors.subtext }}>{meta ?? category}</Text>
        {price!=null && <Text style={{ fontSize:13, fontWeight:'700', color:colors.accentStrong }}>${price}</Text>}
      </View>
    </View>
  );
}
