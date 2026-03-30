import React from "react";
import { View, Text, Pressable, ViewStyle } from "react-native";
import { Link, useRouter, type Href } from "expo-router";
import { color, radius, space, text as T, shadow } from "../theme/tokens";
import { fireHaptic, HapticIntent } from "@/haptics";
export default function Tile({ title, subtitle, href, onPress, left, right, style, disabled }:{
  title:string; subtitle?:string; href?:string; onPress?:()=>void; left?:React.ReactNode; right?:React.ReactNode; style?:ViewStyle; disabled?:boolean;
}) {
  const router = useRouter();
  const inner = (
    <View style={[{
      borderWidth:1, borderColor:color.border, borderRadius:radius.lg, backgroundColor: disabled ? color.border + '30' : color.bg,
      padding: space.lg, gap: space.sm,
    }, shadow.card, style]}>
      <View style={{ flexDirection:"row", alignItems:"center", justifyContent:"space-between" }}>
        <View style={{ flexDirection:"row", alignItems:"center", gap: space.sm }}>
          {left ? <View style={{ width: 28, alignItems:"center" }}>{left}</View> : null}
          <Text style={{ fontSize:T.lg, fontWeight:"700" }}>{title}</Text>
        </View>
        {right ?? null}
      </View>
      {subtitle ? <Text style={{ color: color.subtext }}>{subtitle}</Text> : null}
    </View>
  );
  if (href && !disabled) return <Link href={href as Href} asChild><Pressable onPress={() => fireHaptic(HapticIntent.CONFIRMATION_LIGHT)} accessibilityRole="button" accessibilityLabel={title}>{inner}</Pressable></Link>;
  return <Pressable onPress={() => { if (disabled) return; fireHaptic(HapticIntent.CONFIRMATION_LIGHT); if (onPress) return onPress(); if (href) router.push(href as Href); }} disabled={disabled} accessibilityRole="button" accessibilityLabel={title}>{inner}</Pressable>;
}
