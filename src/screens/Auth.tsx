import { useState } from 'react';
import { View, Alert } from 'react-native';
import { supabase } from "@/lib/supabaseClient";
import Input from '../components/Input';
import Button from '../components/Button';
import { colors } from '../theme/tokens';

export default function Auth(){
  const [email,setEmail]=useState(''); const [password,setPassword]=useState('');
  const signUp=async()=>{ const {error}=await supabase.auth.signUp({email,password}); if(error) Alert.alert(error.message); else Alert.alert('Check email to confirm'); };
  const signIn=async()=>{ const {error}=await supabase.auth.signInWithPassword({email,password}); if(error) Alert.alert(error.message); };
  return (<View style={{flex:1,backgroundColor:colors.bg,padding:24,gap:16}}>
    <Input label="Email" value={email} onChangeText={setEmail} placeholder="you@domain.com"/>
    <Input label="Password" value={password} onChangeText={setPassword} placeholder="••••••••" secureTextEntry/>
    <Button title="Sign In" onPress={signIn}/>
    <Button title="Create Account" onPress={signUp} variant="ghost"/>
  </View>);
}
