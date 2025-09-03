import { View, Alert } from 'react-native';
import { colors } from '../theme/tokens';
import { supabase } from '../lib/supabase';
import ActionTile from '../components/ActionTile';

export default function Settings(){
  const signOut = async ()=>{
    const { error } = await supabase.auth.signOut();
    if (error) Alert.alert('Sign out error', error.message);
  };

  return (
    <View style={{ flex:1, backgroundColor: colors.bg, padding:24, gap:16 }}>
      <ActionTile
        title="Log Out"
        subtitle="Sign out of your account"
        icon="log-out-outline"
        onPress={signOut}
      />
    </View>
  );
}
