import React, { useMemo, useRef, useState } from 'react';
import { View, Text, PanResponder, LayoutChangeEvent } from 'react-native';
import Svg, { Path, Rect, Defs, ClipPath, G, Line, Circle } from 'react-native-svg';
import { theme } from '@/theme';
export type Point = { t: number; y: number };
export default function LineChart({ data, height=160, padding=16, gridY=4, gridX=6 }: { data: Point[]; height?:number; padding?:number; gridY?:number; gridX?:number; }) {
  const [w, setW] = useState(0); const [cursor, setCursor] = useState<{x:number;y:number;i:number}|null>(null);
  const onLayout = (e:LayoutChangeEvent)=> setW(e.nativeEvent.layout.width);
  const { path, scaleX, scaleY, hi, lo } = useMemo(()=>{
    const xs=data.map(d=>d.t), ys=data.map(d=>d.y);
    const minX=Math.min(...xs), maxX=Math.max(...xs); const minY0=Math.min(...ys), maxY0=Math.max(...ys);
    const padY=(maxY0-minY0)*0.08 || 1; const minY=minY0-padY, maxY=maxY0+padY;
    const scaleX=(x:number)=> padding + (w>0? (x-minX)/(maxX-minX||1)*(w-padding*2):0);
    const scaleY=(y:number)=>{ const h=height-padding*2; const v=padding+(1-(y-minY)/(maxY-minY||1))*h; return Math.max(padding, Math.min(height-padding, v)); };
    let d=''; data.forEach((p,i)=>{ const X=scaleX(p.t), Y=scaleY(p.y); d += (i===0?`M ${X} ${Y}`:` L ${X} ${Y}`); });
    let hiI=0, loI=0; for(let i=1;i<data.length;i++){ if(data[i].y>data[hiI].y) hiI=i; if(data[i].y<data[loI].y) loI=i; }
    return { path:d, scaleX, scaleY, hi:hiI, lo:loI };
  },[data,w,height,padding]);
  const pan=useRef(PanResponder.create({ onStartShouldSetPanResponder:()=>true, onPanResponderGrant:e=>move(e.nativeEvent.locationX), onPanResponderMove=e=>move(e.nativeEvent.locationX), onPanResponderRelease:()=>setCursor(null) })).current;
  const move=(x:number)=>{ if(w<=0) return; let nearest=0, best=Infinity; data.forEach((p,i)=>{ const px=padding+(w-padding*2)*((p.t-data[0].t)/((data[data.length-1].t-data[0].t)||1)); const d=Math.abs(px-x); if(d<best){best=d; nearest=i;} }); const p=data[nearest]; setCursor({x:scaleX(p.t), y:scaleY(p.y), i:nearest}); };
  const fmt=(n:number)=> new Intl.NumberFormat('en-US',{style:'currency',currency:'EUR',minimumFractionDigits:0,maximumFractionDigits:0}).format(n);
  return (
    <View onLayout={onLayout} style={{ backgroundColor: theme.colors.card, borderWidth:1, borderColor: theme.colors.border }}>
      <Svg height={height} width="100%" {...pan.panHandlers}>
        <Defs><ClipPath id="clip"><Rect x={padding} y={padding} width={Math.max(0, w-padding*2)} height={height-padding*2} /></ClipPath></Defs>
        <G>{Array.from({length:gridY+1}).map((_,i)=>{ const y=padding+i*(height-padding*2)/gridY; return <Line key={'gy'+i} x1={padding} x2={Math.max(padding,w-padding)} y1={y} y2={y} stroke={theme.colors.border} strokeWidth={1}/>; })}
           {Array.from({length:gridX+1}).map((_,i)=>{ const x=padding+i*(Math.max(0,w-padding*2))/gridX; return <Line key={'gx'+i} y1={padding} y2={height-padding} x1={x} x2={x} stroke={theme.colors.border} strokeWidth={1}/>; })}</G>
        <G clipPath="url(#clip)"><Path d={path} stroke={theme.colors.navy} strokeWidth={2} fill="none"/></G>
        {data.length>0 && (<><Circle cx={scaleX(data[hi].t)} cy={scaleY(data[hi].y)} r={3} fill={theme.colors.up}/><Circle cx={scaleX(data[lo].t)} cy={scaleY(data[lo].y)} r={3} fill={theme.colors.down}/></>)}
        {cursor && (<G pointerEvents="none"><Line x1={cursor.x} x2={cursor.x} y1={padding} y2={height-padding} stroke={theme.colors.navy} strokeDasharray="3 3"/><Circle cx={cursor.x} cy={cursor.y} r={4} fill="#fff" stroke={theme.colors.navy}/></G>)}
      </Svg>
      {cursor && (<View style={{ position:'absolute', left:Math.max(padding, Math.min((cursor.x-48),(w-96))), top:6, backgroundColor:'#fff', borderWidth:1, borderColor: theme.colors.border, paddingHorizontal:8, paddingVertical:4 }}>
        <Text style={{ color: theme.colors.navy, fontWeight:'700' }}>{fmt(data[cursor.i].y)}</Text>
      </View>)}
    </View>
  );
}
