import { useState } from 'react';
import { View, Text, ActivityIndicator, Pressable, Dimensions } from 'react-native';
import { FlashList } from '@shopify/flash-list';
import SearchBar from '@/components/SearchBar';
import ItemCard from '@/components/ItemCard';
import { colors, fonts, spacing } from '../theme/tokens';
import useMarketplace from '../hooks/useMarketplace';
import { useNavigation } from '@react-navigation/native';

export default function Marketplace(){
  const [search, setSearch] = useState('');
  const [order, setOrder] = useState<'new'|'price_asc'|'price_desc'>('new');
  const { rows, loading, refreshing, refresh, loadMore } = useMarketplace({ search, order });

  const nav = useNavigation<any>();
  const width = Dimensions.get('window').width;
  const col = 2;
  const gap = spacing(1);
  const cardW = Math.floor((width - spacing(2)*2 - gap*(col-1)) / col);

  if (loading && !rows.length) return <View style={{flex:1,justifyContent:'center',alignItems:'center'}}><ActivityIndicator/></View>;

  return (
    <View style={{ flex:1, backgroundColor: colors.bg, padding: spacing(2), gap: spacing(2) }}>
      <SearchBar value={search} onChange={setSearch} placeholder="Search listings…" />
      <View style={{ flexDirection:'row', gap:8 }}>
        {(['new','price_asc','price_desc'] as const).map(o=>{
          const active = order===o;
          return (
            <Pressable key={o} onPress={()=>setOrder(o)} style={{
              paddingHorizontal:10, paddingVertical:6, borderRadius:999, borderWidth:1,
              borderColor: active? '#14B8A6' : '#E2E8F0', backgroundColor: active? '#ECFEFF':'#F8FAFC'
            }}>
              <Text style={{ fontSize:12, fontWeight:'700', color: active? '#14B8A6' : '#64748B' }}>{o.toUpperCase()}</Text>
            </Pressable>
          );
        })}
      </View>

      {!rows.length ? (
        <View style={{flex:1,justifyContent:'center',alignItems:'center'}}><Text style={fonts.small}>No listings found.</Text></View>
      ) : (
        <FlashList
          data={rows}
          numColumns={col}
          key={col}
          estimatedItemSize={cardW+110}
          contentContainerStyle={{ gap, paddingTop:4 }}
          refreshing={refreshing}
          onRefresh={refresh}
          onEndReached={loadMore}
          onEndReachedThreshold={0.5}
          renderItem={({item})=>(
            <Pressable onPress={()=>nav.navigate('ListingDetail',{ listing:item })} style={{ width: cardW }}>
              <ItemCard
                title={item.title}
                category={item.currency}
                image_url={item.image_url}
                price={item.price}
                meta={item.condition || null}
              />
            </Pressable>
          )}
        />
      )}
    </View>
  );
}
