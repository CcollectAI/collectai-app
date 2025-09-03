import { View } from 'react-native';
import { colors, radius } from '../theme/tokens';

export default function SkeletonCard(){
  return (
    <View style={{ borderRadius:radius.lg, borderWidth:1, borderColor:colors.border, overflow:'hidden' }}>
      <View style={{ height:150, backgroundColor:'#E5E7EB' }}/>
      <View style={{ padding:12, gap:8 }}>
        <View style={{ height:16, width:'70%', backgroundColor:'#E5E7EB', borderRadius:8 }}/>
        <View style={{ height:14, width:'40%', backgroundColor:'#E5E7EB', borderRadius:8 }}/>
      </View>
    </View>
  );
}
