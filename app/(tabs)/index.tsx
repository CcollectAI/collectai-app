import { useMemo, useState } from 'react';
import { View, Text, ScrollView } from 'react-native';
import Card from '@/components/Card';
import LineChart from '@/components/LineChart';
import RangeToggle from '@/components/RangeToggle';
import { theme } from '@/theme';

type Row = { name: string; pct: number; price: number; };
const fmtEUR_US = (n: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'EUR' }).format(n);

const now = Date.now();
const base = 12400;
const genData = (len: number) =>
  Array.from({ length: len }, (_, i) => ({ t: now - (len - i) * 60_000, v: base + i * 3.5 + Math.sin(i / 7) * 8 }));

const DATASETS = { '1D': genData(90), '7D': genData(120), '30D': genData(180) };
const SAMPLE: Row[] = [
  { name: 'PSA 9 Charizard', pct: 2.4, price: 1820 },
  { name: 'Funko Pop #01', pct: -1.1, price: 260 },
  { name: 'Hot Wheels RLC', pct: 0.7, price: 145 },
  { name: 'LEGO Millennium Falcon', pct: 0.3, price: 980 },
];

export default function Portfolio() {
  const [range, setRange] = useState<'1D'|'7D'|'30D'>('7D');
  const data = DATASETS[range];
  const total = useMemo(() => Math.round(data[data.length - 1]?.v || 0), [data]);

  // % Today from 1D
  const oneDay = DATASETS['1D'];
  const pctToday = useMemo(() => {
    if (!oneDay.length) return 0;
    const first = oneDay[0].v, last = oneDay[oneDay.length - 1].v;
    return ((last - first) / (first || 1)) * 100;
  }, [oneDay]);

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.lg, gap: theme.spacing.lg }}>
      {/* Collection value (US numerics for EUR) */}
      <Card style={{ padding: theme.spacing.md, gap: 4 }}>
        <Text style={{ color: theme.colors.navy, fontSize: 20, fontWeight: '900' }}>Collection Value</Text>
        <Text style={{ color: theme.colors.navy, fontSize: 18, fontWeight: '700' }}>{fmtEUR_US(total)}</Text>
        <Text style={{ fontSize: 12, color: pctToday >= 0 ? theme.colors.up : theme.colors.down }}>
          {(pctToday >= 0 ? '+' : '') + pctToday.toFixed(2)}% Today
        </Text>
      </Card>

      {/* Chart */}
      <Card style={{ padding: theme.spacing.md, gap: theme.spacing.md }}>
        <RangeToggle options={['1D','7D','30D']} value={range} onChange={(v) => setRange(v as any)} />
        <LineChart data={data} />
      </Card>

      {/* 3) "Items" title encased in a white box */}
      <Card style={{ padding: theme.spacing.sm }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '800' }}>Items</Text>
      </Card>

      {/* Items table (no '%' header; % under name) */}
      <Card style={{ padding: theme.spacing.md }}>
        <View style={{ flexDirection: 'row', paddingBottom: theme.spacing.sm, borderBottomWidth: 1, borderColor: theme.colors.border }}>
          <Text style={{ flex: 1, color: theme.colors.subtext, fontWeight: '700' }}>Name</Text>
          <Text style={{ width: 100, textAlign: 'right', color: theme.colors.subtext, fontWeight: '700' }}>Price</Text>
        </View>
        {SAMPLE.sort((a,b)=>b.price - a.price).map((row, idx) => (
          <View key={idx} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.sm, borderBottomWidth: idx < SAMPLE.length - 1 ? 1 : 0, borderColor: theme.colors.border }}>
            <View style={{ flex: 1, paddingRight: theme.spacing.lg }}>
              <Text style={{ color: theme.colors.navy, fontWeight: '600' }}>{row.name}</Text>
              <Text style={{ fontSize: 12, marginTop: 2, color: row.pct >= 0 ? theme.colors.up : theme.colors.down }}>
                {(row.pct >= 0 ? '+' : '') + row.pct.toFixed(2)}%
              </Text>
            </View>
            <Text style={{ width: 100, textAlign: 'right', color: theme.colors.navy, fontWeight: '700' }}>
              {fmtEUR_US(row.price)}
            </Text>
          </View>
        ))}
      </Card>

      {/* 4) Watchlist restored under Items */}
      <Card style={{ padding: theme.spacing.md, gap: theme.spacing.sm }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Watchlist</Text>
        <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>No items yet.</Text>
        <View style={{ alignItems: 'center', marginTop: theme.spacing.sm }}>
          <View style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>+ Add to watchlist</Text>
          </View>
        </View>
      </Card>
    </ScrollView>
  );
}
