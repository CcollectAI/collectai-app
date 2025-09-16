import { useState } from 'react';
import { View, Text, ScrollView, Pressable, TextInput, Alert, Image } from 'react-native';
import CompactSelect from '@/components/CompactSelect'; import Card from '@/components/Card'; import Icon from '@/components/Icon'; import { theme } from '@/theme';
import { predictFromImage } from '@/lib/predict'; import { addItem } from '@/store/items'; import { router } from 'expo-router';
const CATEGORIES=['Pokémon','Funko','LEGO','Diecast','Sports Cards','Comics','Other']; const CONDITIONS=['New','Near Mint','Good','Used','Damaged']; const YEARS=Array.from({length:35},(_,i)=>String(2025-i));
async function pickFromLibrary():Promise<string|undefined>{ try{ const IP=await import('expo-image-picker'); const res=await IP.launchImageLibraryAsync({quality:0.7,allowsEditing:false}); if(!res.canceled && res.assets?.[0]?.uri) return res.assets[0].uri; }catch{ Alert.alert('Gallery unavailable','expo-image-picker not installed yet.'); } }
async function capturePhoto():Promise<string|undefined>{ try{ const IP=await import('expo-image-picker'); const perm=await IP.requestCameraPermissionsAsync(); if(!perm.granted){ Alert.alert('Permission','Camera permission denied.'); return; } const res=await IP.launchCameraAsync({quality:0.7}); if(!res.canceled && res.assets?.[0]?.uri) return res.assets[0].uri; }catch{ Alert.alert('Camera unavailable','expo-image-picker not installed yet.'); } }
export default function Add(){
  const [imageUri,setImageUri]=useState<string|undefined>(); const [cat,setCat]=useState('Pokémon'); const [title,setTitle]=useState(''); const [year,setYear]=useState('2024'); const [condition,setCondition]=useState('Near Mint'); const [price,setPrice]=useState(''); const [notes,setNotes]=useState('');
  const onPick=async()=>{ const uri=await pickFromLibrary(); if(uri){ setImageUri(uri); const pred=await predictFromImage(uri); applyPred(pred);} }; const onCapture=async()=>{ const uri=await capturePhoto(); if(uri){ setImageUri(uri); const pred=await predictFromImage(uri); applyPred(pred);} };
  function applyPred(pred:{category:string; title?:string; priceHint?:number}){ setCat(pred.category); if(pred.title && !title) setTitle(pred.title); if(pred.priceHint && !price) setPrice(String(Math.round(pred.priceHint))); }
  const save=async()=>{ const p=Number(price||0); if(!title||!cat||!p){ Alert.alert('Missing','Add title, category and price.'); return; } await addItem({ category:cat, name:title, price:p, pct:0 }); Alert.alert('Saved','Item added to your Items.',[{text:'OK',onPress:()=>router.push('/(tabs)/items')}]); };
  return (
  <ScrollView style={{flex:1, backgroundColor: theme.colors.bg}} contentContainerStyle={{padding:theme.spacing.xl,gap:theme.spacing.xl}}>
    <Card style={{gap:theme.spacing.md}}>
      <Text style={{color:theme.colors.navy,fontWeight:'700'}}>Use AI Prediction & Take a picture</Text>
      <View style={{flexDirection:'row',gap:12,flexWrap:'wrap'}}>
        <Pressable onPress={onCapture} style={{borderWidth:1,borderColor:theme.colors.navy,paddingVertical:8,paddingHorizontal:16,flexDirection:'row',alignItems:'center',gap:8}}><Icon name="add-circle-outline"/><Text style={{color:theme.colors.navy,fontWeight:'700'}}>Capture</Text></Pressable>
        <Pressable onPress={onPick} style={{borderWidth:1,borderColor:theme.colors.navy,paddingVertical:8,paddingHorizontal:16,flexDirection:'row',alignItems:'center',gap:8}}><Icon name="image-outline"/><Text style={{color:theme.colors.navy,fontWeight:'700'}}>Choose from Gallery</Text></Pressable>
      </View>
      {imageUri ? <Image source={{uri:imageUri}} style={{width:'100%',height:220,borderWidth:1,borderColor:theme.colors.border}}/> : null}
    </Card>
    <Card style={{gap:theme.spacing.md}}>
      <Text style={{color:theme.colors.navy,fontWeight:'700'}}>Manual details</Text>
      <View style={{flexDirection:'row',gap:theme.spacing.md,flexWrap:'wrap'}}>
        <CompactSelect title="Category" options={CATEGORIES} value={cat} onChange={setCat} searchable/>
        <CompactSelect title="Year" options={YEARS} value={year} onChange={setYear}/>
        <CompactSelect title="Condition" options={CONDITIONS} value={condition} onChange={setCondition}/>
      </View>
      <LabeledInput label="Title" value={title} onChangeText={setTitle} placeholder="e.g., PSA 9 Charizard"/>
      <LabeledInput label="Price (€)" value={price} onChangeText={setPrice} keyboardType="numeric" placeholder="e.g., 1200"/>
      <LabeledInput label="Notes" value={notes} onChangeText={setNotes} placeholder="Optional notes…" multiline/>
      <View style={{flexDirection:'row',gap:12}}>
        <Pressable onPress={save} style={{borderWidth:1,borderColor:theme.colors.navy,paddingVertical:10,paddingHorizontal:16}}><Text style={{color:theme.colors.navy,fontWeight:'700'}}>Save</Text></Pressable>
      </View>
    </Card>
  </ScrollView>);
}
function LabeledInput(props:{label:string}&React.ComponentProps<typeof TextInput>){ const {label,...rest}=props; return(<View style={{gap:6}}>
  <Text style={{color:theme.colors.navy,fontWeight:'700'}}>{label}</Text>
  <TextInput {...rest} placeholderTextColor={theme.colors.subtext} style={{borderWidth:1,borderColor:theme.colors.border,padding:10,backgroundColor:'#fff'}}/></View>);
}
