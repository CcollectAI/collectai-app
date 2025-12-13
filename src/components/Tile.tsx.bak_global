import React from "react";
import { View, Text, Pressable, ViewStyle } from "react-native";
import { Link, useRouter } from "expo-router";
import { color, radius, space, text as T, shadow } from "../theme/tokens";
export default function Tile({ title, subtitle, href, onPress, left, right, style, disabled }:{
  title:string; subtitle?:string; href?:string; onPress?:()=>void; left?:React.ReactNode; right?:React.ReactNode; style?:ViewStyle; disabled?:boolean;
}) {
  const router = useRouter();
  const inner = (
    <View style={[{
      borderWidth:1, borderColor:color.border, borderRadius:radius.lg, backgroundColor: disabled ? "#f9fafb" : color.bg,
      padding: space.lg, gap: space.sm,
    }, shadow.card, style]}>
      <View style={{ flexDirection:"row", alignItems:"center", justifyContent:"space-between" }}>
        <View style={{ flexDirection:"row", alignItems:"center", gap: space.sm }}>
          {left ? <View style={{ width: 28, alignItems:"center" }}>{left}</View> : null}
          <Text style={{ fontSize:T.lg, fontWeight:"700" }}>{title}</Text>
        </View>
        {right ?? null}
      </View>
      {subtitle ? <Text style={{ color: color.textMuted }}>{subtitle}</Text> : null}
    </View>
  );
  if (href && !disabled) return <Link href={href} asChild><Pressable accessibilityRole="button">{inner}</Pressable></Link>;
  return <Pressable onPress={() => { if (disabled) return; if (onPress) return onPress(); if (href) router.push(href); }} disabled={disabled}>{inner}</Pressable>;
}
