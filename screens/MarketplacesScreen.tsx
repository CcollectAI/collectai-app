import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Button, Alert, FlatList } from 'react-native';
import { supabase } from '../lib/supabase';
import { Category } from '../types/category';
import { CategoryMarketplaces } from '../lib/marketplaces';

type Props = { route?: any; itemId?: string; itemCategory?: Category; };

export default function MarketplacesScreen({ route, itemId, itemCategory }: Props) {
  const id = itemId ?? route?.params?.itemId;
  const cat = itemCategory ?? route?.params?.itemCategory;

  const [links, setLinks] = useState<any[]>([]);
  const [marketplace_key, setMarketplaceKey] = useState<string>((cat && CategoryMarketplaces[cat]?.[0]) ?? 'ebay');
  const [url, setUrl] = useState('');
  const [query, setQuery] = useState('');

  async function load() {
    const { data, error } = await supabase
      .from('marketplace_links')
      .select('*')
      .eq('item_id', id)
      .order('created_at', { ascending: false });
    if (error) Alert.alert('Error', error.message);
    else setLinks(data ?? []);
  }

  async function addLink() {
    const { error } = await supabase.from('marketplace_links').insert([{
      item_id: id, marketplace_key, url: url || null, query: query || null
    }]);
    if (error) Alert.alert('Error', error.message);
    else { setUrl(''); setQuery(''); load(); }
  }

  async function removeLink(linkId: number) {
    const { error } = await supabase.from('marketplace_links').delete().eq('id', linkId);
    if (error) Alert.alert('Error', error.message);
    else load();
  }

  useEffect(() => { load(); }, []);

  return (
    <View style={{ padding: 16, gap: 12 }}>
      <Text style={{ fontWeight: '700' }}>Add Marketplace Link</Text>
      {cat ? <Text>Suggested: {CategoryMarketplaces[cat].join(', ')}</Text> : null}
      <TextInput
        value={marketplace_key}
        onChangeText={setMarketplaceKey}
        placeholder="e.g., ebay"
        style={{ borderWidth: 1, borderColor: '#ddd', padding: 8, borderRadius: 8 }}
      />
      <TextInput
        value={url}
        onChangeText={setUrl}
        placeholder="Paste URL (optional)"
        style={{ borderWidth: 1, borderColor: '#ddd', padding: 8, borderRadius: 8 }}
      />
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Saved search keywords (optional)"
        style={{ borderWidth: 1, borderColor: '#ddd', padding: 8, borderRadius: 8 }}
      />
      <Button title="Save Link" onPress={addLink} />

      <Text style={{ fontWeight: '700', marginTop: 16 }}>Existing Links</Text>
      <FlatList
        data={links}
        keyExtractor={(x) => String(x.id)}
        renderItem={({ item }) => (
          <View style={{ borderWidth: 1, borderColor: '#eee', padding: 8, borderRadius: 8, marginBottom: 8 }}>
            <Text>marketplace: {item.marketplace_key}</Text>
            {item.url ? <Text numberOfLines={1}>url: {item.url}</Text> : null}
            {item.query ? <Text numberOfLines={1}>query: {item.query}</Text> : null}
            <View style={{ marginTop: 6 }}>
              <Button title="Delete" onPress={() => removeLink(item.id)} />
            </View>
          </View>
        )}
      />
    </View>
  );
}
