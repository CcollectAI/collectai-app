import React from "react";
import { View } from "react-native";
import Header from "../../src/components/Header";
import PortfolioChart from "../../src/components/PortfolioChart";
import ActionTile from "../../src/components/ActionTile";
import { theme } from "../../src/theme";
import { useRouter } from "expo-router";

export default function Home() {
  const router = useRouter();

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      {/* Visual brand header (the gear is also in headerRight from Tabs layout) */}
      <Header title="Collectors" />

      {/* Portfolio card with chart + delta badge */}
      <PortfolioChart />

      {/* 2×2 quick actions */}
      <View style={{ flexDirection: "row", flexWrap: "wrap", paddingHorizontal: theme.spacing.lg }}>
        <ActionTile label="New Listing"   emoji="🧾" onPress={() => router.push("/listings/new")} />
        <ActionTile label="Categories"    emoji="🗂️" onPress={() => router.push("/categories")} />
        <ActionTile label="My Collection" emoji="📦" onPress={() => router.push("/collection")} />
        <ActionTile label="Marketplace"   emoji="🛒" onPress={() => router.push("/listings")} />
      </View>
    </View>
  );
}
