import { useMemo, useState } from 'react';
import { View, Text, ActivityIndicator, Pressable, Dimensions } from 'react-native';
import { FlashList } from '@shopify/flash-list';
import SearchBar from '@/components/SearchBar';
import CategoryChips from '@/components/CategoryChips';
import ItemCard from '@/components/ItemCard';
import SkeletonCard from '@/components/SkeletonCard';
import { fonts, colors, spacing } from '../theme/tokens';
import useItems from '../hooks/useItems';
import { useNavigation } from '@react-navigation/native';
import ActionTile from '@/components/ActionTile';

export default function Items(){
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [order, setOrder] = useState<'new'|'old'|'title'>('new');
  const [grid, setGrid] = useState(true);

  const { items, loading, error, refreshing, refresh, loadMore } = useItems({ search, category, order, limit: grid? 24 : 16 });
  const nav = useNavigation<any>();
  const width = Dimensions.get('window').width;
  const col = grid ? 2 : 1;
  const gap = spacing(1);
  const cardW = useMemo(()=> Math.floor((width - spacing(2)*2 - gap*(col-1)) / col), [width, col, gap]);

  return (
    <View style={{ flex:1, backgroundColor: colors.bg, padding: spacing(2), gap: spacing(2) }}>
      <SearchBar value={search} onChange={setSearch} />
      <CategoryChips value={category} onChange={setCategory} />

      <View style={{ flexDirection:'row', justifyContent:'space-between', alignItems:'center' }}>
        <Text style={fonts.small}>Order:</Text>
        <View style={{ flexDirection:'row', gap:8 }}>
          {(['new','old','title'] as const).map(o=>{
            const active = order===o;
            return (
              <Pressable key={o} onPress={()=>setOrder(o)} style={{
                paddingHorizontal:10, paddingVertical:6, borderRadius:999, borderWidth:1,
                borderColor: active? colors.accentStrong : colors.border, backgroundColor: active? '#ECFEFF':'#F8FAFC'
              }}>
                <Text style={{ fontSize:12, fontWeight:'700', color: active? colors.accentStrong : '#64748B' }}>{o.toUpperCase()}</Text>
              </Pressable>
            );
          })}
          <Pressable onPress={()=>setGrid(g=>!g)} style={{ paddingHorizontal:10, paddingVertical:6, borderRadius:999, borderWidth:1, borderColor:colors.border }}>
            <Text style={{ fontSize:12 }}>{grid?'GRID':'LIST'}</Text>
          </Pressable>
        </View>
      </View>
   <ActionTile
      title="Add Item"
      subtitle="Catalog a new collectible"
      icon="add-circle-outline"
      onPress={() => nav.navigate('Add')}
   />

      {loading && items.length===0 ? (
        <FlashList
          data={Array.from({length: grid? 6:4})}
          estimatedItemSize={grid? (cardW+100) : 120}
          numColumns={col}
          key={col}
          contentContainerStyle={{ gap, paddingTop:4 }}
          renderItem={()=> <View style={{ width:cardW }}><SkeletonCard/></View>}
        />
      ) : error ? (
        <View style={{ padding: 16 }}><Text style={{ color: 'red' }}>{error}</Text></View>
      ) : items.length===0 ? (
        <View style={{ flex:1, justifyContent:'center', alignItems:'center' }}>
          <Text style={fonts.small}>No items found. Try changing filters or adding an item.</Text>
        </View>
      ) : (
        <FlashList
          data={items}
          estimatedItemSize={grid? (cardW+110) : 120}
          numColumns={col}
          key={col}
          contentContainerStyle={{ gap, paddingTop:4 }}
          onRefresh={refresh}
          refreshing={refreshing}
          onEndReached={loadMore}
          onEndReachedThreshold={0.5}
          renderItem={({item})=>(
            <Pressable onPress={()=>nav.navigate('ItemDetail', { item })} style={{ width:cardW }}>
             <ItemCard
               title={item.title}
               category={item.category}
               image_url={item.image_url}
               price={item.purchase_price||null}
               meta={[
                 item.condition || null,
                 item.year ? String(item.year) : null,
                 item.series || null,
              ].filter(Boolean).join(' • ') || null}
          />
       </Pressable>

          )}
        />
      )}
    </View>
  );
}
