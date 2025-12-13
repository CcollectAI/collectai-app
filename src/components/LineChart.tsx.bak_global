import React, { useMemo, useState } from 'react';
import { View, LayoutChangeEvent } from 'react-native';
import Svg, { Path, Rect, Line as SvgLine, Defs, ClipPath } from 'react-native-svg';

export type Point = { t: number; y: number };

type Props = {
  data: Point[];
  height?: number;   // total svg height
  padding?: number;  // inner padding of plot area
  stroke?: string;
};

export default function LineChart({ data, height=180, padding=16, stroke='#0B3D91' }: Props) {
  const [w, setW] = useState(0);
  const onLayout = (e: LayoutChangeEvent) => setW(Math.floor(e.nativeEvent.layout.width));
  const plotW = Math.max(0, w - padding*2);
  const plotH = Math.max(0, height - padding*2);

  const { minX, maxX, minY, maxY } = useMemo(()=>{
    if (data.length === 0) return { minX:0, maxX:1, minY:0, maxY:1 };
    const xs = data.map(p=>p.t);
    const ys = data.map(p=>p.y);
    let minY = Math.min(...ys), maxY = Math.max(...ys);
    if (minY === maxY) { const pad = Math.max(1, Math.abs(minY)*0.05); minY-=pad; maxY+=pad; }
    return { minX: Math.min(...xs), maxX: Math.max(...xs), minY, maxY };
  },[data]);

  const sx = (t:number)=> padding + (plotW * ((t - minX) / ((maxX - minX) || 1)));
  const sy = (y:number)=> padding + plotH - (plotH * ((y - minY) / ((maxY - minY) || 1)));

  const path = useMemo(()=>{
    if (data.length === 0) return '';
    return data.map((p,i)=> `${i===0?'M':'L'}${sx(p.t)},${sy(p.y)}`).join(' ');
  },[data, w, height, padding, minX, maxX, minY, maxY]);

  // Subtle grid
  const hLines = Array.from({length:4},(_,i)=> padding + (plotH/4)*i);
  const vLines = Array.from({length:3},(_,i)=> padding + (plotW/3)*i);

  return (
    <View style={{ height }} onLayout={onLayout}>
      {w>0 && (
        <Svg width={w} height={height}>
          {/* Background plot rect */}
          <Rect x={padding} y={padding} width={plotW} height={plotH} fill="#FFFFFF" stroke="#E5E7EB" strokeWidth={1} />
          {/* Grid */}
          {hLines.map((y,i)=> <SvgLine key={'h'+i} x1={padding} y1={y} x2={padding+plotW} y2={y} stroke="#E5E7EB" strokeWidth={1} />)}
          {vLines.map((x,i)=> <SvgLine key={'v'+i} x1={x} y1={padding} x2={x} y2={padding+plotH} stroke="#F1F5F9" strokeWidth={1} />)}
          {/* Clip so the line never exceeds the box */}
          <Defs><ClipPath id="clip"><Rect x={padding} y={padding} width={plotW} height={plotH} /></ClipPath></Defs>
          {path ? <Path d={path} clipPath="url(#clip)" stroke={stroke} strokeWidth={1.5} fill="none" strokeLinejoin="round" strokeLinecap="round" /> : null}
        </Svg>
      )}
    </View>
  );
}
