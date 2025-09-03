import { Pressable, View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radius, shadow } from '../theme/tokens';

export default function ActionTile({
  title, subtitle, icon="pricetags-outline", onPress,
}:{ title:string; subtitle?:string; icon?:keyof typeof Ionicons.glyphMap; onPress:()=>void }){
  return (
    <Pressable
      onPress={onPress}
      style={{
        backgroundColor:'#fff',
        borderRadius: radius.lg,
        borderWidth: 1,
        borderColor: colors.border,
        padding: 16,
        ...shadow.card,
        flexDirection:'row',
        alignItems:'center',
        gap:12
      }}
    >
      <View style={{ width:40, height:40, borderRadius:12, backgroundColor:'#ECFEFF', alignItems:'center', justifyContent:'center', borderWidth:1, borderColor:'#BAF2EA' }}>
        <Ionicons name={icon} size={20} color={colors.accentStrong} />
      </View>
      <View style={{ flex:1 }}>
        <Text style={{ fontSize:16, fontWeight:'800', color:colors.text }}>{title}</Text>
        {subtitle ? <Text style={{ fontSize:12, color:'#64748B', marginTop:4 }}>{subtitle}</Text> : null}
      </View>
      <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
    </Pressable>
  );
}
