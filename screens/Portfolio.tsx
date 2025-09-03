import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, RefreshControl } from 'react-native';
import { fetchItems, fetchLatestPrices, computeTotals } from '../lib/portfolio';

export default function Portfolio() {
  const [rows, setRows] = useState<any[]>([]);
  const [totals, setTotals] = useState({ cost: 0, value: 0, pnl: 0 });
  const [byCat, setByCat] = useState<{[k:string]:{cost:number,value:number,pnl:number}}>({});
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    const items = await fetchItems();
    const prices = await fetchLatestPrices(items.map(i => i.id));
    const { rows, totals } = computeTotals(items, prices);
    setRows(rows);
    setTotals(totals);
    const agg: any = {};
    for (const r of rows) {
      agg[r.category] ||= { cost:0, value:0, pnl:0 };
      agg[r.category].cost += r.acquisition_price||0;
      agg[r.category].value += r.latest_price||0;
      agg[r.category].pnl += r.pnl||0;
    }
    setByCat(agg);
  }

  useEffect(() => { load(); }, []);
  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  const top = [...rows].sort((a,b)=> (b.pnl - a.pnl)).slice(0,5);

  return (
    <View style={{ flex: 1, padding: 12 }}>
      <View style={{ borderWidth:1, borderColor:'#eee', borderRadius:12, padding:12, marginBottom:12 }}>
        <Text style={{ fontWeight:'700', fontSize:16 }}>Portfolio</Text>
        <Text>Total Cost: €{totals.cost.toFixed(2)}</Text>
        <Text>Current Value: €{totals.value.toFixed(2)}</Text>
        <Text style={{ fontWeight:'700' }}>P/L: €{totals.pnl.toFixed(2)} {totals.pnl>=0 ? '📈' : '📉'}</Text>
      </View>

      <View style={{ borderWidth:1, borderColor:'#eee', borderRadius:12, padding:12, marginBottom:12 }}>
        <Text style={{ fontWeight:'700', marginBottom:6 }}>By Category</Text>
        {Object.entries(byCat).map(([k,v])=>(
          <Text key={k}>{k}: €{v.value.toFixed(2)} (P/L €{v.pnl.toFixed(2)})</Text>
        ))}
      </View>

      <Text style={{ fontWeight:'700', marginBottom:6 }}>Top Movers</Text>
      <FlatList
        data={top}
        keyExtractor={(x)=>x.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        renderItem={({item})=>(
          <View style={{ borderWidth:1, borderColor:'#eee', borderRadius:12, padding:12, marginBottom:10 }}>
            <Text style={{ fontWeight:'700' }}>{item.title}</Text>
            <Text style={{ color:'#666' }}>{item.category}</Text>
            <Text>P/L: €{item.pnl.toFixed(2)}</Text>
          </View>
        )}
      />
    </View>
  );
}

