import { ScrollView, Pressable, Text, View } from 'react-native';
import { colors, radius } from '../theme/tokens';

const CATS = ['all','pokemon','funko','diecast'];

export default function CategoryChips({
  value, onChange
}:{ value:string; onChange:(c:string)=>void }){
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap:8 }}>
      {CATS.map(c=>{
        const active = value===c;
        return (
          <Pressable key={c} onPress={()=>onChange(c)}>
            <View style={{
              paddingHorizontal:12, paddingVertical:8, borderRadius:radius.xl,
              borderWidth:1, borderColor: active? colors.accentStrong : colors.border,
              backgroundColor: active? '#ECFEFF' : '#F8FAFC',
            }}>
              <Text style={{ color: active? colors.accentStrong : '#64748B', fontWeight:'700', fontSize:12 }}>{c.toUpperCase()}</Text>
            </View>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}
