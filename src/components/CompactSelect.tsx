import { useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, Text, TextInput, View, Dimensions } from 'react-native';
import Icon from '@/components/Icon';
import { theme } from '@/theme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';

const TIFFANY = '#81D8D0';
const TIFFANY_LIGHT = '#E6F7F5';

type Props = { title?:string; value?:string|null; options:string[]; placeholder?:string; onChange:(v:string)=>void; searchable?:boolean; };

export default function CompactSelect({ title, value, options, placeholder='Select…', onChange, searchable=false }:Props) {
  const triggerRef = useRef<View>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [anch, setAnch] = useState<{x:number;y:number;w:number;h:number}|null>(null);
  const show = () => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); try { // @ts-ignore
    triggerRef.current?.measureInWindow?.((x:number,y:number,w:number,h:number)=>{ setAnch({x,y,w,h}); setOpen(true); }); } catch { setAnch(null); setOpen(true); } };
  const hide = () => { setOpen(false); setQuery(''); };
  const filtered = query ? options.filter(o=>o.toLowerCase().includes(query.toLowerCase())) : options;
  const { width:SW, height:SH } = Dimensions.get('window'); const POPOVER_W=280; const left=Math.max(8, Math.min((anch?.x ?? 16), SW-POPOVER_W-8)); const topBase=(anch ? anch.y+anch.h+6 : 120); const maxH=Math.max(160, Math.min(360, SH-topBase-16)); const top=Math.min(topBase, SH-maxH-8);
  return (<>
    <AnimatedPressable ref={triggerRef} onPress={show} style={{ alignSelf: 'flex-start' }} accessibilityRole="button" accessibilityLabel={`${title || 'Select'}: ${value || placeholder}`}>
      <View style={{
        backgroundColor: theme.colors.card,
        borderWidth: 1,
        borderColor: theme.colors.border,
        borderRadius: 10,
        paddingVertical: 8,
        paddingHorizontal: 12,
        flexDirection: 'row',
        alignItems: 'center',
        gap: 6,
      }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '600', fontSize: 14 }}>{value || placeholder}</Text>
        <Icon name="chevron-down" />
      </View>
    </AnimatedPressable>
    <Modal visible={open} transparent animationType="fade" onRequestClose={hide}>
      <Pressable onPress={hide} style={{ flex:1, backgroundColor:'rgba(0,0,0,0.15)' }} accessibilityRole="button" accessibilityLabel="Close dropdown">
        <Pressable onPress={()=>{}} accessibilityRole="none" style={{
          position:'absolute', top, left, width:POPOVER_W,
          backgroundColor: theme.colors.card,
          borderWidth:1, borderColor: theme.colors.border,
          borderRadius: 14,
          padding:14, maxHeight:maxH,
          shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.12, shadowRadius: 12, elevation: 6,
        }}>
          {title ? (<View style={{ flexDirection:'row', alignItems:'center', justifyContent:'space-between', marginBottom:10 }}>
            <Text style={{ color: theme.colors.navy, fontWeight:'700', fontSize: 15 }}>{title}</Text>
            <Pressable onPress={hide} accessibilityRole="button" accessibilityLabel="Close">
              <Icon name="close" />
            </Pressable>
          </View>) : null}
          {searchable ? (
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder="Search…"
              placeholderTextColor={theme.colors.subtext}
              accessibilityLabel="Search options"
              style={{
                borderWidth:1, borderColor: theme.colors.border,
                borderRadius: 8,
                padding:8, backgroundColor:'#fff', marginBottom:10, fontSize: 14,
              }}
            />
          ) : null}
          <ScrollView keyboardShouldPersistTaps="handled">
            {filtered.map((opt, idx) => {
              const selected = value === opt;
              return (
                <AnimatedPressable key={opt} onPress={()=>{ fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onChange(opt); hide(); }} accessibilityRole="button" accessibilityLabel={`${opt}${selected ? ', selected' : ''}`}>
                  <View style={{
                    paddingVertical:10, paddingHorizontal: 8,
                    flexDirection:'row', alignItems:'center', justifyContent:'space-between',
                    borderTopWidth: idx===0?0:1, borderColor: theme.colors.border,
                    backgroundColor: selected ? TIFFANY_LIGHT : 'transparent',
                    borderRadius: selected ? 8 : 0,
                    marginVertical: selected ? 1 : 0,
                  }}>
                    <Text style={{ color: selected ? TIFFANY : theme.colors.navy, fontWeight: selected?'700':'500', fontSize: 14 }}>{opt}</Text>
                    {selected ? <Icon name="checkmark" color={TIFFANY} /> : null}
                  </View>
                </AnimatedPressable>
              );
            })}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  </>);
}
