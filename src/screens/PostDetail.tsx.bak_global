import { useState } from 'react';
import { View, Text, TextInput, Pressable, FlatList } from 'react-native';
import { colors, spacing, fonts } from '../theme/tokens';
import useComments from '../hooks/useComments';

export default function PostDetail({ route }:any){
  const { post } = route.params;
  const { rows, loading, add } = useComments(post.id);
  const [text,setText]=useState('');

  const submit=()=>{
    if(text.trim()){ add(text.trim()); setText(''); }
  };

  return (
    <View style={{ flex:1, backgroundColor:colors.bg, padding:spacing(2) }}>
      <Text style={fonts.h2}>{post.content}</Text>
      {loading ? <Text>Loading comments…</Text> :
        <FlatList
          data={rows}
          keyExtractor={c=>c.id}
          renderItem={({item})=>(
            <View style={{ paddingVertical:6, borderBottomWidth:1, borderBottomColor:colors.border }}>
              <Text style={fonts.body}>{item.content}</Text>
              <Text style={fonts.small}>{new Date(item.created_at).toLocaleString()}</Text>
            </View>
          )}
        />
      }
      <View style={{ flexDirection:'row', marginTop:12, gap:8 }}>
        <TextInput
          value={text}
          onChangeText={setText}
          placeholder="Add a comment…"
          style={{ flex:1, borderWidth:1, borderColor:colors.border, borderRadius:8, padding:8 }}
        />
        <Pressable onPress={submit} style={{ backgroundColor:colors.accentStrong, paddingHorizontal:16, justifyContent:'center', borderRadius:8 }}>
          <Text style={{ color:'#fff', fontWeight:'700' }}>Send</Text>
        </Pressable>
      </View>
    </View>
  );
}
