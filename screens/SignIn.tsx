import React, { useState } from 'react';
import { View, Text, TextInput, Button, Alert } from 'react-native';
import { supabase } from '../lib/supabase';

export default function SignIn() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);

  async function sendMagic() {
    try {
      const { error } = await supabase.auth.signInWithOtp({ email });
      if (error) throw error;
      setSent(true);
      Alert.alert('Check your email', 'Magic link sent.');
    } catch (e:any) { Alert.alert('Error', e.message ?? String(e)); }
  }

  return (
    <View style={{ padding:16, gap:12 }}>
      <Text style={{ fontWeight:'700', fontSize:18 }}>Sign in</Text>
      <TextInput value={email} onChangeText={setEmail} placeholder="you@example.com"
        style={{ borderWidth:1,borderColor:'#ddd',padding:10,borderRadius:8 }} autoCapitalize="none" keyboardType="email-address" />
      <Button title={sent ? 'Resend Link' : 'Send Magic Link'} onPress={sendMagic} />
      <Text style={{ color:'#666' }}>Use the link on this device to finish sign-in.</Text>
    </View>
  );
}
