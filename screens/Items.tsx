import React, { useState, useLayoutEffect } from 'react';
import { View, Text, ActivityIndicator, Button, FlatList, RefreshControl, TextInput, Switch } from 'react-native';
import SearchBar from '../components/SearchBar';
import CategoryChips from '../components/CategoryChips';
import ItemCard from '../components/ItemCard';
import useItems from '../hooks/useItems';
import AddItemForm from '../components/AddItemForm';
import BulkBar from '../components/BulkBar';
import { useNavigation } from '@react-navigation/native';
import type { Category } from '../types/category';
import { useSettings } from '../src/settings/SettingsContext';

type SortKey = 'created_at' | 'latest_price' | 'title';

export default function Items() {
  const navigation = useNavigation<any>();
  const [search, setSearch] = useState('');
  const [cat, setCat] = useState<Category | 'all'>('all');
  const [grid, setGrid] = useState(false);
  const [sortBy, setSortBy] = useState<SortKey>('created_at');
  const [sortDir, setSortDir] = useState<'asc'|'desc'>('desc');
  const { items, loading, error, refresh, loadMore } = useItems({ search, category: cat, pageSize: grid ? 30 : 20, sortBy, sortDir });
  const [showAdd, setShowAdd] = useState(false);
  const { settings } = useSettings();
  const [grid, setGrid] = useState(settings.defaultGrid);
  const [sortBy, setSortBy] = useState<typeof settings.defaultSortBy>(settings.defaultSortBy);
  const [sortDir, setSortDir] = useState<typeof settings.defaultSortDir>(settings.defaultSortDir);
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useLayoutEffect(() => {    navigation.setOptions({
      headerRight: () => (
        <View style={{ flexDirection:'row', gap: 8 }}>
          <Button title={selectMode ? "Done" : "Select"} onPress={()=>{
            setSelectMode(s=>!s);
            if (selectMode) setSelected(new Set( }} />
          <Button title="Settings" onPress={()=>navigation.navigate('Settings')} />
          <Button title="Alerts" onPress={()=>navigation.navigate('Alerts')} />
          <Button title="Import" onPress={()=>navigation.navigate('ImportCSV')} />
          <Button title="Archived" onPress={()=>navigation.navigate('Archived')} />
          <Button title="Export" onPress={()=>navigation.navigate('ExportAll')} />
          <Button title="Onboard" onPress={()=>navigation.navigate('Onboarding')} />
          <Button title="Scan" onPress={()=>navigation.navigate('ScanAdd')} />
        </View>
      )
    });
  }, [navigation, selectMode]);

  const openMarket = (id: string) => navigation.navigate('Marketplaces', { itemId: id });

  const numColumns = grid ? 2 : 1;
  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  };

  return (
    <View style={{ flex:1 }}>
      <SearchBar value={search} onChange={setSearch} />
      <CategoryChips value={cat} onChange={setCat} />
      <CategoryChips value={cat} onChange={setCat} /* 👇 new prop */ pinned={settings.pinnedCategories} />

      <View style={{ paddingHorizontal:12, paddingBottom:8, gap:8 }}>
        <View style={{ flexDirection:'row', alignItems:'center', justifyContent:'space-between' }}>
          <View style={{ flexDirection:'row', alignItems:'center', gap:8 }}>
            <Text>Grid</Text>
            <Switch value={grid} onValueChange={setGrid} />
          </View>
          <View style={{ flexDirection:'row', alignItems:'center', gap:8 }}>
            <TextInput
              value={sortBy}
              onChangeText={(t)=>{ if (t==='created_at'||t==='latest_price'||t==='title') setSortBy(t as SortKey); }}
              placeholder="created_at | latest_price | title"
              style={{ minWidth:160, borderWidth:1, borderColor:'#ddd', padding:8, borderRadius:8 }}
            />
            <TextInput
              value={sortDir}
              onChangeText={(t)=>{ if (t==='asc'||t==='desc') setSortDir(t as 'asc'|'desc'); }}
              placeholder="asc | desc"
              style={{ width:90, borderWidth:1, borderColor:'#ddd', padding:8, borderRadius:8 }}
            />
          </View>
        </View>

        {!selectMode && (
          <>
            <Button title={showAdd ? "Close Add Item" : "Add Item"} onPress={()=>setShowAdd(s=>!s)} />
            {showAdd ? <AddItemForm onCreated={(id)=>{ setShowAdd(false); navigation.navigate('ItemDetail',{ id }); }} /> : null}
          </>
        )}
      </View>

      {error ? <Text style={{ color:'red', paddingHorizontal:12 }}>{error}</Text> : null}
      {loading && items.length===0 ? <ActivityIndicator style={{ marginTop: 20 }} /> : null}

      <FlatList
        style={{ paddingHorizontal:12 }}
        data={items}
        key={numColumns}
        numColumns={numColumns}
        columnWrapperStyle={grid ? { justifyContent:'space-between' } : undefined}
        keyExtractor={(it)=>it.id}
        refreshControl={<RefreshControl refreshing={false} onRefresh={refresh} />}
        renderItem={({item})=>(
          <ItemCard
            item={item}
            layout={grid ? 'grid' : 'list'}
            onPress={()=>navigation.navigate('ItemDetail', { id: item.id })}
            openMarket={openMarket}
            selectable={selectMode}
            selected={selected.has(item.id)}
            onToggleSelect={toggleSelect}
          />
        )}
        onEndReachedThreshold={0.4}
        onEndReached={loadMore}
      />

      {selectMode ? <BulkBar ids={[...selected]} reload={refresh} /> : null}
    </View>
  );
}
