import { View, ViewProps } from 'react-native';
import { colors, radius, shadow } from '../theme/tokens';
export default function Card({style,...p}:ViewProps){
  return <View style={[{backgroundColor:colors.surface,borderRadius:radius.lg,borderWidth:1,borderColor:colors.border,padding:16,...shadow.card},style as any]} {...p} />;
}
