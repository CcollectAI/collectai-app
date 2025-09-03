import { View, Text, Image, Pressable } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import Avatar from './Avatar';
import { colors, radius, shadow, fonts } from '../theme/tokens';

export default function PostCard({
  id, content, image_url, userName, liked, likeCount, onLike,
}:{
  id?: string;
  content?: string;
  image_url?: string|null;
  userName?: string;
  liked?: boolean;
  likeCount?: number;
  onLike?: ()=>void;
}){
  const nav = useNavigation<any>();

  return (
    <Pressable
      onPress={()=> nav.navigate('PostDetail', { post:{ id, content, image_url, userName } })}
      style={{ borderRadius: radius.lg, overflow:'hidden' }}
    >
      <View style={{ backgroundColor:'#fff', borderWidth:1, borderColor:colors.border, borderRadius:radius.lg, ...shadow.card }}>
        <View style={{ flexDirection:'row', alignItems:'center', gap:10, padding:12 }}>
          <Avatar name={userName} />
          <Text style={{ fontWeight:'700', color:colors.text }}>{userName||'User'}</Text>
        </View>

        {image_url ? (
          <Image source={{ uri:image_url }} style={{ width:'100%', height:220 }} />
        ) : null}

        {content ? (
          <Text style={{ padding:12, color:colors.text }}>{content}</Text>
        ) : null}

        <View style={{ flexDirection:'row', alignItems:'center', justifyContent:'space-between', padding:12, borderTopWidth:1, borderTopColor:colors.border }}>
          <Text style={fonts.small}>{likeCount||0} likes</Text>
          <Pressable
            onPress={onLike}
            style={{
              paddingHorizontal:12,
              paddingVertical:8,
              borderRadius:999,
              borderWidth:1,
              borderColor: liked? colors.accentStrong: colors.border,
            }}
          >
            <Text style={{ color: liked? colors.accentStrong : colors.subtext, fontWeight:'700' }}>
              {liked ? 'Liked' : 'Like'}
            </Text>
          </Pressable>
        </View>
      </View>
    </Pressable>
  );
}
