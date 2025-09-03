import React, { useMemo } from 'react';
import { ScrollView, Text, Pressable, View } from 'react-native';
import { Category, CategoryList, CategoryLabels } from '../types/category';

export default function CategoryChips({
  value, onChange, pinned=[]
}: { value?: Category | 'all'; onChange: (c: Category | 'all') => void; pinned?: Category[] }) {
  const order = useMemo(()=>{
    const base = ['all', ...CategoryList] as const;
    const star = pinned.filter(p=> (CategoryList as readonly string[]).includes(p));
    const rest = base.filter((c:any)=> c==='all' || !star.includes(c));
    return (['all', ...star, ...rest.filter(c=>c!=='all')]) as (Category|'all')[];
  }, [pinned]);

  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ paddingVertical: 8 }}>
      {order.map((c:any) => {
        const active = value === c || (!value && c==='all');
        const starred = (pinned as readonly string[]).includes(c);
        return (
          <Pressable key={c} onPress={()=>onChange(c)} style={{ paddingHorizontal:12,paddingVertical:6, borderRadius:999, marginRight:8, borderWidth:1, borderColor: active?'#111':'#ddd', backgroundColor: active?'#eee':'#fff' }}>
            <Text>{c==='all' ? 'All' : (starred ? `★ ${CategoryLabels[c]}` : CategoryLabels[c])}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}
