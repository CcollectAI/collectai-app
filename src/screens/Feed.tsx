import { View, Text, ActivityIndicator, RefreshControl } from 'react-native';
import { FlashList } from '@shopify/flash-list';
import useFeed from '../hooks/useFeed';
import PostCard from '../components/PostCard';
import { colors, fonts, spacing } from '../theme/tokens';
import { useEffect } from 'react';
import ActionTile from '../components/ActionTile';
import { useNavigation } from '@react-navigation/native';

export default function Feed(){
  const { rows, loading, refreshing, refresh, loadMore, toggleLike } = useFeed();
  const nav = useNavigation<any>();

  useEffect(()=>{},[]);

  if (loading && rows.length===0) {
    return (
      <View style={{flex:1,justifyContent:'center',alignItems:'center'}}>
        <ActivityIndicator/>
      </View>
    );
  }

  if (!rows.length) {
    return (
      <View style={{flex:1,justifyContent:'center',alignItems:'center'}}>
        <Text style={fonts.small}>No posts yet.</Text>
      </View>
    );
  }

  return (
   <View style={{ flex:1, backgroundColor: colors.bg, padding: spacing(2) }}>
    <ActionTile
      title="New Post"
      subtitle="Share your latest pickup"
      icon="create-outline"
      onPress={() => nav.navigate('NewPost')}
  />
     <FlashList
        data={rows}
        estimatedItemSize={300}
        contentContainerStyle={{ gap: spacing(1) }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
        onEndReached={loadMore}
        onEndReachedThreshold={0.6}
        renderItem={({item})=>(
          <PostCard
            id={item.id}
            userName={'Collector'}
            content={item.content || undefined}
            image_url={item.image_url || undefined}
            liked={item.liked}
            likeCount={item.like_count}
            onLike={()=>toggleLike(item.id)}
          />
        )}
      />
    </View>
  );
}
