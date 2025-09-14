import React, { useMemo, useState } from "react";
import { SafeAreaView, View, Text, Pressable, ScrollView } from "react-native";
import { theme } from "@/theme";

type Point = { t: number; v: number };
const MOCK_1D: Point[] = [ {t:0,v:2700},{t:1,v:2710},{t:2,v:2705},{t:3,v:2725},{t:4,v:2718},{t:5,v:2729},{t:6,v:2725} ];
const MOCK_7D: Point[] = [ {t:0,v:2650},{t:1,v:2675},{t:2,v:2690},{t:3,v:2708},{t:4,v:2715},{t:5,v:2722},{t:6,v:2725} ];
const MOCK_30D: Point[] = Array.from({length: 30}, (_,i)=>({t:i,v:2600 + Math.sin(i/3)*20 + i}));

function fmtMoney(n:number){ return new Intl.NumberFormat("en-US",{minimumFractionDigits:2,maximumFractionDigits:2}).format(n); }
function pct(oldV:number,newV:number){ if(!oldV) return 0; return ((newV-oldV)/oldV)*100; }

function GridLine({ topPct }: { topPct: number }) {
  return (
    <View
      pointerEvents="none"
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: `${topPct}%`,
        borderTopWidth: 1,
        borderTopColor: theme.colors.border,
      }}
    />
  );
}

function SimpleLine({ data, height=160 }:{ data:Point[]; height?:number }) {
  // No external libs; emulate a thicker line using small segments/dots + overlay.
  const padding = 12;
  const h = height, w = 320; // chart area width; ScrollView parent will center it
  const min = Math.min(...data.map(d=>d.v));
  const max = Math.max(...data.map(d=>d.v));
  const span = Math.max(1, max - min);

  const pts = data.map((d,i)=>{
    const x = padding + ( (w - padding*2) * (i / Math.max(1, (data.length-1))) );
    const y = padding + ( (h - padding*2) * (1 - (d.v - min)/span) );
    return {x,y,v:d.v};
  });

  return (
    <View style={{ width: w, height: h, backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border }}>
      {/* Grid */}
      <GridLine topPct={25} />
      <GridLine topPct={50} />
      <GridLine topPct={75} />

      {/* Min/Max labels */}
      <View style={{ position: "absolute", left: 8, top: 8 }}>
        <Text style={{ color: theme.colors.subtext, fontSize: theme.font.small }}>€{fmtMoney(max)}</Text>
      </View>
      <View style={{ position: "absolute", left: 8, bottom: 8 }}>
        <Text style={{ color: theme.colors.subtext, fontSize: theme.font.small }}>€{fmtMoney(min)}</Text>
      </View>

      {/* "Line" – dot segments for a thicker, sharper look */}
      {pts.map((p,i)=>(
        <View key={i} style={{
          position: "absolute",
          left: p.x-1,
          top: p.y-1,
          width: 2,
          height: 2,
          backgroundColor: theme.colors.brand.base
        }}/>
      ))}
      {pts.slice(1).map((p,i)=>{
        const p0 = pts[i];
        const dx = p.x - p0.x;
        const dy = p.y - p0.y;
        const len = Math.hypot(dx,dy) || 1;
        const angle = Math.atan2(dy,dx) * 180/Math.PI;
        return (
          <View
            key={`seg-${i}`}
            style={{
              position: "absolute",
              left: p0.x,
              top: p0.y,
              width: len,
              height: 2,
              backgroundColor: theme.colors.brand.base,
              transform: [{ rotateZ: `${angle}deg` }],
              transformOrigin: "left center" as any,
            }}
          />
        );
      })}
    </View>
  );
}

export default function PortfolioScreen(){
  const [range, setRange] = useState<"1D"|"7D"|"30D">("1D");
  const data = range==="1D"?MOCK_1D:range==="7D"?MOCK_7D:MOCK_30D;
  const latest = data[data.length-1]?.v ?? 0;
  const first = data[0]?.v ?? 0;
  const change = pct(first, latest);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <ScrollView contentContainerStyle={{ padding: theme.spacing.lg, gap: theme.spacing.lg }}>
        {/* Title & value */}
        <View style={{ gap: 6 }}>
          <Text style={{ fontSize: theme.font.title, fontWeight: "800", color: theme.colors.brand.base }}>
            Collection Value
          </Text>
          <Text style={{ fontSize: 28, fontWeight: "800", color: theme.colors.text }}>
            €{fmtMoney(latest)}
          </Text>
          <Text style={{ fontSize: theme.font.small, fontWeight: "600", color: change>=0?theme.colors.success:theme.colors.danger }}>
            {change>=0?"+":""}{change.toFixed(2)}% today
          </Text>
        </View>

        {/* Chart + range selector */}
        <View style={{ alignItems: "center", gap: theme.spacing.sm }}>
          <SimpleLine data={data} height={180} />
          <View style={{ flexDirection: "row", gap: 8, alignSelf: "flex-end" }}>
            {(["1D","7D","30D"] as const).map(r => (
              <Pressable
                key={r}
                onPress={()=>setRange(r)}
                style={{
                  paddingHorizontal: 10, paddingVertical: 6,
                  borderWidth: 1, borderColor: r===range?theme.colors.brand.base:theme.colors.border,
                  backgroundColor: r===range?theme.colors.brand.soft:theme.colors.card
                }}
              >
                <Text style={{ fontWeight: "700", color: r===range?theme.colors.brand.base:theme.colors.text }}>{r}</Text>
              </Pressable>
            ))}
          </View>
        </View>

        {/* Collection list (tightened spacing & padding around boxes) */}
        <View style={{ gap: theme.spacing.sm }}>
          <Text style={{ fontSize: theme.font.h2, fontWeight: "800", color: theme.colors.brand.base }}>
            Collection
          </Text>

          {[
            { name:"Charizard Holo 1999", value:1240.00, delta:+3.10 },
            { name:"Lego Millennium Falcon 75192", value:680.00, delta:-1.40 },
            { name:"PSA 10 Mewtwo", value:810.00, delta:+0.80 },
          ].map((row, i)=>(
            <View key={i} style={{
              backgroundColor: theme.colors.card,
              borderWidth: 1, borderColor: theme.colors.border,
              paddingHorizontal: theme.spacing.md, paddingVertical: theme.spacing.sm,
            }}>
              <Text style={{ fontWeight: "700", color: theme.colors.text }}>{row.name}</Text>
              <View style={{ flexDirection:"row", justifyContent:"space-between", marginTop: 4 }}>
                <Text style={{ color: row.delta>=0?theme.colors.success:theme.colors.danger, fontSize: theme.font.small }}>
                  {row.delta>=0?"+":""}{row.delta.toFixed(2)}%
                </Text>
                <Text style={{ fontWeight:"700", color: theme.colors.text }}>€{fmtMoney(row.value)}</Text>
              </View>
            </View>
          ))}

          {/* Watchlist call-to-action centered at bottom */}
          <View style={{ alignItems:"center", marginTop: theme.spacing.md }}>
            <Pressable style={{
              paddingHorizontal: 14, paddingVertical: 10,
              borderWidth: 1, borderColor: theme.colors.brand.base,
              backgroundColor: theme.colors.brand.soft
            }}>
              <Text style={{ fontWeight: "800", color: theme.colors.brand.base }}>+ Add to watchlist</Text>
            </Pressable>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
