import React from "react";
import { SafeAreaView, View, Text, ScrollView, Pressable } from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";
import { theme } from "@/theme";

function fmtMoney(n:number){ return new Intl.NumberFormat("en-US",{minimumFractionDigits:2,maximumFractionDigits:2}).format(n); }

const DATA = [
  { category:"Pokémon", total: 2050.00, items:[
    { name:"Charizard Holo 1999", value:1240.00, delta:+3.10 },
    { name:"PSA 10 Mewtwo", value:810.00, delta:+0.80 },
  ]},
  { category:"LEGO", total: 680.00, items:[
    { name:"Millennium Falcon 75192", value:680.00, delta:-1.40 },
  ]},
];

export default function ItemsScreen(){
  return (
    <SafeAreaView style={{ flex:1, backgroundColor: theme.colors.bg }}>
      <ScrollView contentContainerStyle={{ padding: theme.spacing.lg, gap: theme.spacing.lg }}>
        {/* Title row + Share button */}
        <View style={{ flexDirection:"row", alignItems:"center" }}>
          <Text style={{ flex:1, fontSize: theme.font.title, fontWeight:"800", color: theme.colors.brand.base }}>
            Items
          </Text>
          <Pressable style={{ paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card }}>
            <Text style={{ fontWeight:"700", color: theme.colors.text }}>Share</Text>
          </Pressable>
        </View>

        {DATA.map((g, gi)=>(
          <View key={gi} style={{ gap: theme.spacing.sm }}>
            {/* Category header with shield badge on the right */}
            <View style={{
              flexDirection:"row",
              alignItems:"center",
              backgroundColor: theme.colors.card,
              borderWidth: 1, borderColor: theme.colors.border,
              paddingHorizontal: theme.spacing.md, paddingVertical: theme.spacing.sm,
            }}>
              <Text style={{ fontWeight:"800", color: theme.colors.text }}>{g.category}</Text>
              <View style={{ marginLeft: "auto" }}>
                <Ionicons name="shield" size={16} color="#C0C0C0" />
              </View>
            </View>

            {/* Items in this category */}
            {g.items.map((it, ii)=>(
              <View key={ii} style={{
                backgroundColor: theme.colors.card,
                borderWidth: 1, borderColor: theme.colors.border,
                paddingHorizontal: theme.spacing.md, paddingVertical: theme.spacing.sm,
              }}>
                <Text style={{ fontWeight:"700", color: theme.colors.text }}>{it.name}</Text>
                <View style={{ flexDirection:"row", justifyContent:"space-between", marginTop: 4 }}>
                  <Text style={{ fontSize: theme.font.small, color: it.delta>=0?theme.colors.success:theme.colors.danger }}>
                    {it.delta>=0?"+":""}{it.delta.toFixed(2)}%
                  </Text>
                  <Text style={{ fontWeight:"700", color: theme.colors.text }}>€{fmtMoney(it.value)}</Text>
                </View>
              </View>
            ))}

            {/* Category total aligned bottom-right */}
            <View style={{ alignItems:"flex-end" }}>
              <Text style={{ fontWeight:"800", color: theme.colors.text }}>Total: €{fmtMoney(g.total)}</Text>
            </View>
          </View>
        ))}

        {/* Download Overview centered at the bottom */}
        <View style={{ alignItems:"center", marginTop: theme.spacing.lg }}>
          <Pressable style={{
            paddingHorizontal: 16, paddingVertical: 12,
            borderWidth: 1, borderColor: theme.colors.brand.base,
            backgroundColor: theme.colors.brand.soft
          }}>
            <Text style={{ fontWeight:"800", color: theme.colors.brand.base }}>Download Overview</Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
