import { View, TextInput } from 'react-native';
import { colors, radius } from '../theme/tokens';

export default function SearchBar({
  value, onChange, placeholder='Search items…'
}:{ value:string; onChange:(t:string)=>void; placeholder?:string; }){
  return (
    <View style={{ borderWidth:1, borderColor:colors.border, borderRadius:radius.lg, paddingHorizontal:14, paddingVertical:10, backgroundColor:'#fff' }}>
      <TextInput
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor="#94A3B8"
        style={{ color:colors.text }}
      />
    </View>
  );
}
