import { Pressable, Text, ActivityIndicator } from 'react-native';
import { colors, radius } from '../theme/tokens';

export default function Button({
  title,onPress,loading,variant='primary'
}:{title:string;onPress:()=>void;loading?:boolean;variant?:'primary'|'ghost';}){
  const base={paddingVertical:12,paddingHorizontal:16,borderRadius:radius.md,alignItems:'center'};
  const style=variant==='primary'
    ? { backgroundColor: colors.accentStrong }
    : { backgroundColor:'transparent', borderWidth:1, borderColor:colors.border };

  return (
    <Pressable onPress={onPress} style={[base,style]} disabled={!!loading}>
      {loading
        ? <ActivityIndicator color="#fff"/>
        : <Text style={{ color: variant==='primary' ? '#fff' : colors.text, fontWeight:'700' }}>{title}</Text>}
    </Pressable>
  );
}

