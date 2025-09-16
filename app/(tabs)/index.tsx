import { useMemo, useState } from 'react';
import { View, Text, ScrollView, Pressable } from 'react-native';
import LineChart, { Point } from '@/components/LineChart';
import Card from '@/components/Card';
import Icon from '@/components/Icon';
import { theme } from '@/theme';
const now = Date.now();
const mk=(n:number,step:number,j=0)=>Array.from({length:n},(_,i)=>({t:now-(n-1-i)*step,y:1500+Math.sin(i/3)*60+Math.cos(i/5)*30+(j?(i%7)*2:0)}));
const DATA_1D: Point[] = mk(24,3600*1000), DATA_7D: Point[] = mk(7,24*3600*1000), DATA_30D: Point[] = mk(30,24*3600*1000,1);
const fmt=(n:number)=> new Intl.NumberFormat('en-US',{style:'currency',currency:'EUR',minimumFractionDigits:0,maximumFractionDigits:0}).format(n);
export default function Portfolio(){
  const [range,setRange]=useState<'1D'|'7D'|'30D'>('7D');
  const data=range==='1D'?DATA_1D:range==='7D'?DATA_7D:DATA_30D;
  const total=useMemo(()=>data[data.length-1].y,[data]);
  const pct=useMemo(()=>((data[data.length-1].y-data[0].y)/data[0].y)*100,[data]);
  return(
  <ScrollView style={{flex:1, backgroundColor: theme.colors.bg}} contentContainerStyle={{padding:theme.spacing.lg,gap:theme.spacing.lg}}>
    <View style={{flexDirection:'row',alignItems:'flex-start',justifyContent:'space-between'}}>
      <View>
        <Text style={{color:theme.colors.navy,fontWeight:'800',fontSize:16,backgroundColor:'#fff',paddingHorizontal:8,paddingVertical:4}}>Collection Value</Text>
        <Text style={{color:theme.colors.navy,fontWeight:'700',fontSize:20,marginTop:6}}>{fmt(total)}</Text>
        <Text style={{marginTop:2,color:pct>=0?theme.colors.up:theme.colors.down,fontWeight:'700'}}>{(pct>=0?'+':'')+pct.toFixed(2)}% today</Text>
      </View>
      <View style={{flexDirection:'row',gap:8}}>
        {(['1D','7D','30D'] as const).map(r=>{const a=r===range;return(
          <Pressable key={r} onPress={()=>setRange(r)} style={{backgroundColor:'#fff',borderWidth:1,borderColor:a?theme.colors.navy:theme.colors.border,paddingVertical:4,paddingHorizontal:10}}>
            <Text style={{color:a?theme.colors.navy:theme.colors.subtext,fontWeight:a?'800':'600'}}>{r}</Text>
          </Pressable>
        );})}
      </View>
    </View>
    <LineChart data={data} height={170}/>
    <Text style={{color:theme.colors.navy,fontWeight:'800',backgroundColor:'#fff',alignSelf:'flex-start',paddingHorizontal:8,paddingVertical:4}}>Items</Text>
    <Card>
      <View style={{flexDirection:'row',alignItems:'center',paddingBottom:8,borderBottomWidth:1,borderColor:theme.colors.border}}>
        <Text style={{flex:1,color:theme.colors.subtext,fontWeight:'700'}}>Name</Text>
        <Text style={{width:100,textAlign:'right',color:theme.colors.subtext,fontWeight:'700'}}>Price</Text>
      </View>
      {[{name:'PSA 9 Charizard',pct:+2.4,price:1820},{name:'Pikachu VMAX',pct:-0.8,price:210},{name:'Freddy Funko LE',pct:+1.1,price:320}]
        .map((r,i)=>(
        <View key={i} style={{flexDirection:'row',alignItems:'center',paddingVertical:10,borderBottomWidth:i<2?1:0,borderColor:theme.colors.border}}>
          <View style={{flex:1,paddingRight:12}}>
            <Text style={{color:theme.colors.navy,fontWeight:'600'}}>{r.name}</Text>
            <Text style={{fontSize:12,color:r.pct>=0?theme.colors.up:theme.colors.down,marginTop:2}}>{(r.pct>=0?'+':'')+r.pct.toFixed(2)}%</Text>
          </View>
          <Text style={{width:100,textAlign:'right',color:theme.colors.navy,fontWeight:'700'}}>{fmt(r.price)}</Text>
        </View>))}
    </Card>
    <Card style={{gap:8}}>
      <Text style={{color:theme.colors.navy,fontWeight:'700'}}>Watchlist</Text>
      {[{title:'Charizard alt art PSA 10',price:2400},{title:'LEGO UCS Falcon',price:650}].map((w,i)=>(
        <View key={i} style={{flexDirection:'row',alignItems:'center',justifyContent:'space-between'}}>
          <Text style={{color:theme.colors.navy}}>{w.title}</Text>
          <Text style={{color:theme.colors.subtext}}>{fmt(w.price)}</Text>
        </View>
      ))}
      <Pressable style={{alignSelf:'center',borderWidth:1,borderColor:theme.colors.navy,paddingHorizontal:16,paddingVertical:6,marginTop:4}}>
        <View style={{flexDirection:'row',gap:6,alignItems:'center'}}>
          <Icon name="add-circle-outline"/><Text style={{color:theme.colors.navy,fontWeight:'700'}}>Add to watchlist</Text>
        </View>
      </Pressable>
    </Card>
  </ScrollView>);
}
