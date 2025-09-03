import React, { useEffect, useState } from 'react';
import { View, Text } from 'react-native';
import { VictoryChart, VictoryLine, VictoryAxis } from 'victory-native';
import { supabase } from '../lib/supabase';

type Row = { as_of: string; price: number };

export default function PriceChart({ itemId }: { itemId: string }) {
  const [rows, setRows] = useState<Row[]>([]);

  useEffect(() => {
    (async () => {
      const { data, error } = await supabase
        .from('price_history')
        .select('as_of,price')
        .eq('item_id', itemId)
        .order('as_of', { ascending: true })
        .limit(200);
      if (!error) setRows((data ?? []) as Row[]);
    })();
  }, [itemId]);

  if (!rows.length) return <Text style={{ color:'#666' }}>No price history yet.</Text>;

  const data = rows.map(r => ({ x: new Date(r.as_of), y: r.price }));

  return (
    <View style={{ backgroundColor:'#fff', borderRadius:12, padding:8 }}>
      <Text style={{ fontWeight:'700', marginBottom:6 }}>Price History</Text>
      <VictoryChart>
        <VictoryAxis tickFormat={(t)=>`${t.getMonth()+1}/${t.getDate()}`} />
        <VictoryAxis dependentAxis />
        <VictoryLine data={data} />
      </VictoryChart>
    </View>
  );
}
