import React from "react";
import { View, Text } from "react-native";
import { theme } from "@/theme";
export default function Settings() {
  return <View style={{flex:1,backgroundColor:theme.colors.background,justifyContent:"center",alignItems:"center"}}>
    <Text style={{ color: theme.colors.text, fontSize: 18 }}>Settings (stub)</Text>
  </View>;
}
