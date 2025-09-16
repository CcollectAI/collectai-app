import { View, Text, ScrollView, Pressable, Share, Alert } from 'react-native';
import Icon from '@/components/Icon'; import ShieldBadge from '@/components/ShieldBadge'; import Card from '@/components/Card';
import { theme } from '@/theme'; import { useItemsWithSeed, groupByCategory } from '@/store/items'; import { rowsToCSV, saveCSVAndShare } from '@/export/csv';
const SEED = [{category:'Pokémon',name:'PSA 9 Charizard',pct:2.4,price:1820,tier:'platinum'},{category:'Pokémon',name:'Pikachu VMAX',pct:-0.8,price:210,tier:'platinum'},{category:'Funko',name:'Freddy Funko LE',pct:1.1,price:320,tier:'gold'}] as const;
const fmt=(n:number)=> new Intl.NumberFormat('en-US',{style:'currency',currency:'EUR',minimumFractionDigits:0,maximumFractionDigits:0}).format(n);
export default function Items(){
  const userPlusSeed = useItemsWithSeed(SEED.map(s=>({id:'seed-'+s.name,category:s.category,name:s.name,price:s.price,pct:s.pct,tier:s.tier as any})));
  const groups = groupByCategory(userPlusSeed as any);
  const onShare = async ()=>{ try{ await Share.share({message:'Items overview from Collect AI'});}catch{} };
  const onDownload = async ()=>{ try{
    const rows=(groups as any[]).flatMap(g=>(g.items as any[]).map((it:any)=>({category:g.category,name:it.name,priceEUR:it.price,pct:it.pct})));
    const csv=rowsToCSV(rows);
    const p=await saveCSVAndShare('collectai-items.csv',csv);
    if(p==='unavailable') Alert.alert('Export unavailable','Install FileSystem/Sharing later.');
  }catch(e:any){ Alert.alert('Export error', String(e?.message||e)); } };
  return (
  <ScrollView style={{flex:1, backgroundColor: theme.colors.bg}} contentContainerStyle={{padding:theme.spacing.lg,gap:theme.spacing.lg}}>
    <View style={{flexDirection:'row',alignItems:'center',justifyContent:'space-between'}}>
      <Text style={{color:theme.colors.navy,fontWeight:'800',fontSize:16,backgroundColor:'#fff',paddingHorizontal:8,paddingVertical:4}}>Items</Text>
      <Pressable onPress={onShare} style={{flexDirection:'row',alignItems:'center',gap:6}}><Icon name="share-outline"/><Text style={{color:theme.colors.navy,fontWeight:'700'}}>Share</Text></Pressable>
    </View>
    {groups.map((g:any)=>{ const total=g.items.reduce((s:number,it:any)=>s+it.price,0); return(
      <View key={g.category} style={{gap:theme.spacing.xs}}>
        <Card style={{padding:theme.spacing.md,gap:theme.spacing.sm}}>
          <View style={{flexDirection:'row',alignItems:'center',justifyContent:'space-between',paddingBottom:theme.spacing.xs,borderBottomWidth:1,borderColor:theme.colors.border}}>
            <Text style={{color:theme.colors.navy,fontWeight:'800',fontSize:16}}>{g.category}</Text>
            <ShieldBadge tier={g.tier}/>
          </View>
          <View style={{flexDirection:'row',alignItems:'center',paddingVertical:theme.spacing.xs,borderBottomWidth:1,borderColor:theme.colors.border}}>
            <Text style={{flex:1,color:theme.colors.subtext,fontWeight:'700'}}>Name</Text>
            <Text style={{width:100,textAlign:'right',color:theme.colors.subtext,fontWeight:'700'}}>Price</Text>
          </View>
          {g.items.map((it:any,idx:number)=>(
            <View key={idx} style={{flexDirection:'row',alignItems:'center',paddingVertical:theme.spacing.sm,borderBottomWidth:idx<g.items.length-1?1:0,borderColor:theme.colors.border}}>
              <View style={{flex:1,paddingRight:theme.spacing.md}}>
                <Text style={{color:theme.colors.navy,fontWeight:'600'}}>{it.name}</Text>
                {typeof it.pct==='number' && (<Text style={{fontSize:12,marginTop:2,color:it.pct>=0?theme.colors.up:theme.colors.down}}>{(it.pct>=0?'+':'')+it.pct.toFixed(2)}%</Text>)}
              </View>
              <Text style={{width:100,textAlign:'right',color:theme.colors.navy,fontWeight:'700'}}>{fmt(it.price)}</Text>
            </View>
          ))}
        </Card>
        <View style={{alignItems:'flex-end'}}><Text style={{color:theme.colors.subtext,fontWeight:'700'}}>Total {fmt(total)}</Text></View>
      </View>
    );})}
    <View style={{alignItems:'center',marginTop:theme.spacing.sm,marginBottom:theme.spacing.xl}}>
      <Pressable onPress={onDownload} style={{borderWidth:1,borderColor:theme.colors.navy,paddingVertical:theme.spacing.sm,paddingHorizontal:theme.spacing.xl}}>
        <Text style={{color:theme.colors.navy,fontWeight:'700'}}>Download overview</Text>
      </Pressable>
    </View>
  </ScrollView>);
}
