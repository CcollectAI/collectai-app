import React, { memo } from "react";
import { View, Text } from "react-native";
import { theme } from "@/theme";
import { fmtMoney, fmtPct } from "@/utils/format";

function ItemRow({
  title,
  value,
  changePct,
}: { title: string; value: number; changePct: number }) {
  const pctColor = changePct > 0 ? theme.colors.success : changePct < 0 ? theme.colors.danger : theme.colors.subtext;
  return (
    <View style={{ paddingVertical: 14, paddingHorizontal: 4, borderBottomWidth: 1, borderBottomColor: theme.colors.border }}>
      <Text style={{ fontSize: 14, fontWeight: "600", marginBottom: 6 }}>{title}</Text>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Text style={{ fontSize: 12, color: pctColor }}>{fmtPct(changePct)}</Text>
        <Text style={{ fontWeight: "800", color: theme.colors.text }}>€{fmtMoney(value)}</Text>
      </View>
    </View>
  );
}
export default memo(ItemRow);
