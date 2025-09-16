import { useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, Text, TextInput, View, Dimensions } from 'react-native';
import Icon from '@/components/Icon';
import { theme } from '@/theme';
type Props = { title?:string; value?:string|null; options:string[]; placeholder?:string; onChange:(v:string)=>void; searchable?:boolean; };
export default function CompactSelect({ title, value, options, placeholder='Select…', onChange, searchable=false }:Props) {
  const triggerRef = useRef<View>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [anch, setAnch] = useState<{x:number;y:number;w:number;h:number}|null>(null);
  const show = () => { try { // @ts-ignore
    triggerRef.current?.measureInWindow?.((x:number,y:number,w:number,h:number)=>{ setAnch({x,y,w,h}); setOpen(true); }); } catch { setAnch(null); setOpen(true); } };
  const hide = () => setOpen(false);
  const filtered = query ? options.filter(o=>o.toLowerCase().includes(query.toLowerCase())) : options;
  const { width:SW, height:SH } = Dimensions.get('window'); const POPOVER_W=260; const left=Math.max(8, Math.min((anch?.x ?? 16), SW-POPOVER_W-8)); const topBase=(anch ? anch.y+anch.h+6 : 120); const maxH=Math.max(160, Math.min(320, SH-topBase-16)); const top=Math.min(topBase, SH-maxH-8);
  return (<>
    <Pressable ref={triggerRef} onPress={show} style={{ alignSelf: 'flex-start' }}>
      <View style={{ backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border, paddingVertical: 4, paddingHorizontal: 8, flexDirection: 'row', alignItems: 'center', gap: 4 }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{value || placeholder}</Text>
        <Icon name="chevron-down" />
      </View>
    </Pressable>
    <Modal visible={open} transparent animationType="fade" onRequestClose={hide}>
      <Pressable onPress={hide} style={{ flex:1, backgroundColor:'rgba(11,61,145,0.05)' }}>
        <Pressable onPress={()=>{}} style={{ position:'absolute', top, left, width:POPOVER_W, backgroundColor: theme.colors.card, borderWidth:1, borderColor: theme.colors.border, padding:12, maxHeight:maxH }}>
          {title ? (<View style={{ flexDirection:'row', alignItems:'center', justifyContent:'space-between', marginBottom:8 }}>
            <Text style={{ color: theme.colors.navy, fontWeight:'800' }}>{title}</Text>
            <Icon name="close" />
          </View>) : null}
          {searchable ? (
            <TextInput value={query} onChangeText={setQuery} placeholder="Search…" placeholderTextColor={theme.colors.subtext} style={{ borderWidth:1, borderColor: theme.colors.border, padding:8, backgroundColor:'#fff', marginBottom:8 }} />
          ) : null}
          <ScrollView keyboardShouldPersistTaps="handled">
            {filtered.map((opt, idx) => {
              const selected = value === opt;
              return (
                <Pressable key={opt} onPress={()=>{ onChange(opt); hide(); }}>
                  <View style={{ paddingVertical:12, flexDirection:'row', alignItems:'center', justifyContent:'space-between', borderTopWidth: idx===0?0:1, borderColor: theme.colors.border }}>
                    <Text style={{ color: theme.colors.navy, fontWeight: selected?'800':'600' }}>{opt}</Text>
                    {selected ? <Icon name="checkmark" /> : null}
                  </View>
                </Pressable>
              );
            })}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  </>);
}
