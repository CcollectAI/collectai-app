import React, { useState } from 'react'
import { View, Text, TextInput, Button, FlatList, TouchableOpacity, Linking } from 'react-native'
import { Image } from 'expo-image'
import { useSession } from '@/hooks/useSession'
import { searchEbay, MarketHit } from '@/lib/market'
import { getFlags } from '@/lib/flags'
import { logger } from '@/lib/logger'
import { SUPABASE_URL } from '@/api/config'

type Tab = 'Chat'|'Search'|'Sell'
const Blue = '#40E0D0' // Tiffany-ish
const Navy = '#112B3C'

export default function MarketplaceScreen() {
  const [tab, setTab] = useState<Tab>('Search')
  const { jwt, anonKey } = useSession()
  const base = SUPABASE_URL || ""

  const [query, setQuery] = useState('Pikachu VMAX')
  const [category, setCategory] = useState('Pokemon')
  const [limit, setLimit] = useState(8)
  const [sort, setSort] = useState<'price_asc'|'price_desc'|'time_desc'>('time_desc')

  const [loading, setLoading] = useState(false)
  const [hits, setHits] = useState<MarketHit[]>([])
  const [provider, setProvider] = useState('mock')

  const onSearch = async () => {
    const flags = await getFlags(jwt, anonKey, base);
    setProvider(flags.ebayReal ?  : provider);
    if (!jwt || !anonKey) return
    setLoading(true)
    const res = await searchEbay(jwt, anonKey, query, { category, limit })
    setLoading(false)
    if (!res.ok) { logger.warn(res.error); setHits([]); return }
    const resData = res.data as { provider?: string; hits?: MarketHit[] };
    setProvider(resData.provider || 'mock')
    let arr = resData.hits || []
    if (sort==='price_asc') arr = [...arr].sort((a: MarketHit, b: MarketHit)=>a.price_eur-b.price_eur)
    if (sort==='price_desc') arr = [...arr].sort((a: MarketHit, b: MarketHit)=>b.price_eur-a.price_eur)
    setHits(arr)
  }

  const Seg = ({label}:{label:Tab}) => (
    <TouchableOpacity onPress={() => setTab(label)} style={{ padding: 10, borderBottomWidth: tab===label?3:0, borderBottomColor: Navy }}>
      <Text style={{ fontWeight: tab===label?'700':'400', color: Navy }}>{label}</Text>
    </TouchableOpacity>
  )

  const Card = ({ item }: { item: MarketHit }) => (
    <TouchableOpacity onPress={() => Linking.openURL(item.url)} style={{
      backgroundColor: 'white', padding: 12, marginBottom: 12, borderRadius: 6, borderColor:'#e5e7eb', borderWidth:1, flexDirection:'row', gap:12
    }}>
      <Image source={{ uri: item.image }} style={{ width: 64, height: 64, backgroundColor:'#f3f4f6' }} cachePolicy="disk" transition={150} accessibilityLabel={`Thumbnail of ${item.title}`} />
      <View style={{ flex:1 }}>
        <Text style={{ fontWeight: '700', color: Navy }} numberOfLines={2}>{item.title}</Text>
        <Text style={{ marginTop:4, fontWeight:'600' }}>€ {Number(item.price_eur||0).toFixed(2)}</Text>
        <Text style={{ color:'#64748b', marginTop:2 }}>{new Date(item.ts).toLocaleString()}</Text>
      </View>
    </TouchableOpacity>
  )

  return (
    <View style={{ flex:1, backgroundColor: Blue }}>
      <View style={{ padding:16 }}>
        <View style={{ flexDirection:'row', gap:16, marginBottom:12 }}>
          <Seg label="Chat" /><Seg label="Search" /><Seg label="Sell" />
        </View>

        {tab==='Search' && (
          <View style={{ backgroundColor: 'white', borderRadius: 8, padding: 12 }}>
            <Text style={{ color: Navy, fontWeight:'700', marginBottom:8 }}>Search eBay</Text>
            <TextInput value={query} onChangeText={setQuery} placeholder="Search query"
              style={{ borderWidth:1, borderColor:'#e5e7eb', padding:8, marginBottom:8, borderRadius:6 }} />
            <TextInput value={category} onChangeText={setCategory} placeholder="Category"
              style={{ borderWidth:1, borderColor:'#e5e7eb', padding:8, marginBottom:8, borderRadius:6 }} />

            <View style={{ flexDirection:'row', gap:8, marginBottom:8 }}>
              <TouchableOpacity onPress={()=>setSort('time_desc')} style={{ padding:8, backgroundColor: sort==='time_desc'?Blue:'#eef2f7', borderRadius:6 }}>
                <Text style={{ color: Navy }}>Newest</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={()=>setSort('price_asc')} style={{ padding:8, backgroundColor: sort==='price_asc'?Blue:'#eef2f7', borderRadius:6 }}>
                <Text style={{ color: Navy }}>€ Low→High</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={()=>setSort('price_desc')} style={{ padding:8, backgroundColor: sort==='price_desc'?Blue:'#eef2f7', borderRadius:6 }}>
                <Text style={{ color: Navy }}>€ High→Low</Text>
              </TouchableOpacity>
            </View>

            <Button title={loading?'Searching…':'Search'} onPress={onSearch} />
            <Text style={{ color:'#64748b', marginTop:8 }}>Provider: {provider}</Text>

            <FlatList data={hits} keyExtractor={i=>i.id} renderItem={Card} style={{ marginTop:12, height:'70%' }} />
          </View>
        )}

        {tab==='Chat' && (
          <View style={{ backgroundColor:'white', borderRadius:8, padding:12 }}>
            <Text style={{ color: Navy }}>Chat (mock)</Text>
          </View>
        )}
        {tab==='Sell' && (
          <View style={{ backgroundColor:'white', borderRadius:8, padding:12 }}>
            <Text style={{ color: Navy }}>Sell (mock)</Text>
          </View>
        )}
      </View>
    </View>
  )
}
