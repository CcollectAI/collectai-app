import React, { useState } from 'react';
import { View, Text, Pressable, Button } from 'react-native';
import PriceBadge from './PriceBadge';
import TagPills from './TagPills';
import { truncate } from '../lib/format';
import * as WebBrowser from 'expo-web-browser';
import ThumbImage from './ThumbImage';
import QuickPriceModal from './QuickPriceModal';

type CardItem = {
  id: string;
  title: string;
  category: string;
  acquisition_price?: number | null;
  latest_price?: number | null;
  tag_names?: string[];
  thumb_path?: string | null;
};

type Props = {
  item: CardItem;
  onPress: () => void;
  layout?: 'list' | 'grid';
  openMarket?: (itemId: string) => void;
  selectable?: boolean;
  selected?: boolean;
  onToggleSelect?: (id: string) => void;
};

export default function ItemCard({ item, onPress, layout='list', openMarket, selectable=false, selected=false, onToggleSelect }: Props) {
  const tags = (item.tag_names ?? []) as string[];
  const [showPrice, setShowPrice] = useState(false);
  const toggle = () => onToggleSelect?.(item.id);

  const overlay = selected ? (
    <View pointerEvents="none" style={{ position:'absolute', top:8, right:8, backgroundColor:'#111', paddingHorizontal:8, paddingVertical:2, borderRadius:999 }}>
      <Text style={{ color:'#fff', fontSize:12 }}>✓</Text>
    </View>
  ) : null;

  if (layout === 'grid') {
    return (
      <>
        <Pressable
          onPress={selectable ? toggle : onPress}
          onLongPress={toggle}
          style={{
            width:'48%', borderWidth:1, borderColor: selected ? '#111' : '#eee', borderRadius:12, overflow:'hidden', marginBottom:12
          }}>
          {overlay}
          <ThumbImage path={item.thumb_path} size={120} radius={0} />
          <View style={{ padding:10 }}>
            <Text style={{ fontWeight:'700' }}>{truncate(item.title, 36)}</Text>
            <Text style={{ color:'#666', marginBottom:6 }}>{item.category}</Text>
            <PriceBadge latest={item.latest_price} acq={item.acquisition_price} />
            {!selectable && (
              <View style={{ flexDirection:'row', gap:8, marginTop:8 }}>
                <Button title="Market" onPress={()=>{
                  if (openMarket) { openMarket(item.id); return; }
                  const q = encodeURIComponent(item.title);
                  WebBrowser.openBrowserAsync(`https://www.ebay.com/sch/i.html?_nkw=${q}`);
                }} />
                <Button title="Price +" onPress={()=>setShowPrice(true)} />
              </View>
            )}
          </View>
        </Pressable>
        <QuickPriceModal visible={showPrice} onClose={()=>setShowPrice(false)} itemId={item.id} />
      </>
    );
  }

  return (
    <>
      <Pressable
        onPress={selectable ? toggle : onPress}
        onLongPress={toggle}
        style={{ borderWidth:1, borderColor: selected ? '#111' : '#eee', borderRadius:12, padding:12, marginBottom:12, flexDirection:'row', gap:12 }}>
        {overlay}
        <ThumbImage path={item.thumb_path} />
        <View style={{ flex:1 }}>
          <Text style={{ fontWeight:'700' }}>{truncate(item.title)}</Text>
          <Text style={{ color:'#666' }}>{item.category}</Text>
          <View style={{ marginTop:6 }}>
            <PriceBadge latest={item.latest_price} acq={item.acquisition_price} />
          </View>
          <TagPills tags={tags} />
          {!selectable && (
            <View style={{ flexDirection:'row', gap:8, marginTop:8 }}>
              <Button title="Market" onPress={()=>{
                if (openMarket) { openMarket(item.id); return; }
                const q = encodeURIComponent(item.title);
                WebBrowser.openBrowserAsync(`https://www.ebay.com/sch/i.html?_nkw=${q}`);
              }} />
              <Button title="Price +" onPress={()=>setShowPrice(true)} />
            </View>
          )}
        </View>
      </Pressable>
      <QuickPriceModal visible={showPrice} onClose={()=>setShowPrice(false)} itemId={item.id} />
    </>
  );
}
