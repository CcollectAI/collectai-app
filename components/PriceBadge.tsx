import React from 'react';
import { View, Text } from 'react-native';
import { eur } from '../lib/format';

export default function PriceBadge({ latest, acq }: { latest?: number | null; acq?: number | null }) {
  const last = typeof latest === 'number' ? latest : 0;
  const buy = typeof acq === 'number' ? acq : 0;
  const pnl = last - buy;
  const positive = pnl >= 0;
  return (
    <View style={{ flexDirection:'row', alignItems:'center', gap:8 }}>
      <View style={{ paddingHorizontal:8, paddingVertical:4, borderRadius:8, backgroundColor:'#eee' }}>
        <Text style={{ fontWeight:'700' }}>{eur(last)}</Text>
      </View>
      <View style={{ paddingHorizontal:8, paddingVertical:4, borderRadius:8, backgroundColor: positive ? '#e6f7ea' : '#fdecea' }}>
        <Text style={{ color: positive ? '#0b8a2b' : '#b3261e' }}>
          {positive ? '▲' : '▼'} {eur(pnl)}
        </Text>
      </View>
    </View>
  );
}
