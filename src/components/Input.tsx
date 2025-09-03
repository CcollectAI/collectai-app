import { View, TextInput, Text } from 'react-native';
import { colors, radius } from '../theme/tokens';
export default function Input({label,value,onChangeText,placeholder,secureTextEntry}:{label?:string;value:string;onChangeText:(t:string)=>void;placeholder?:string;secureTextEntry?:boolean;}){
  return <View style={{gap:6}}>
    {label?<Text style={{color:colors.subtext,fontSize:13}}>{label}</Text>:null}
    <TextInput value={value} onChangeText={onChangeText} placeholder={placeholder} placeholderTextColor="#94A3B8" secureTextEntry={secureTextEntry}
      style={{borderWidth:1,borderColor:colors.border,borderRadius:radius.md,paddingHorizontal:14,paddingVertical:12,color:colors.text,backgroundColor:'#fff'}}/>
  </View>;
}
