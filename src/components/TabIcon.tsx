import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '../theme/tokens';

export default function TabIcon({ name, focused, label }:{
  name: keyof typeof Ionicons.glyphMap; focused:boolean; label:string;
}){
  return (
    <View style={{ alignItems:'center', justifyContent:'center' }}>
      <Ionicons name={name} size={22} color={focused ? colors.accentStrong : '#94A3B8'} />
      <Text style={{ fontSize:11, marginTop:4, color: focused? colors.accentStrong : '#64748B' }}>{label}</Text>
    </View>
  );
}
