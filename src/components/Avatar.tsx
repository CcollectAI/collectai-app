import { View, Text } from 'react-native';
import { colors, radius } from '../theme/tokens';

export default function Avatar({ name, size=36 }:{ name?:string; size?:number }){
  const initials = (name||'U').split(' ').map(s=>s[0]).join('').slice(0,2).toUpperCase();
  return (
    <View style={{ width:size, height:size, borderRadius:999, backgroundColor:'#E0F2F1', alignItems:'center', justifyContent:'center', borderWidth:1, borderColor:'#99F6E4' }}>
      <Text style={{ color: colors.accentStrong, fontWeight:'800' }}>{initials}</Text>
    </View>
  );
}
