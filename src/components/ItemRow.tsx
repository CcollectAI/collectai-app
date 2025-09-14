import React from "react";
import { View, Text } from "react-native";
import { theme } from "@/theme";
import { fmtMoney, fmtPct } from "@/utils/format";

export default function ItemRow({
  title,
  value,
  changePct,
}: { title: string; value: number; changePct: number }) {
  const pctColor = changePct > 0 ? theme.colors.up : changePct < 0 ? theme.colors.down : theme.colors.subtext;
  return (
    <View style={{ paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: theme.colors.border }}>
      <Text style={{ ...theme.font.body, fontWeight: "600" }}>{title}</Text>
      <View style={{ flexDirection: "row", justifyContent: "space-between", marginTop: 2 }}>
        <Text style={{ fontSize: 12, color: pctColor }}>{fmtPct(changePct)} today</Text>
        <Text style={{ fontWeight: "800", color: theme.colors.text }}>€{fmtMoney(value)}</Text>
      </View>
    </View>
  );
}
