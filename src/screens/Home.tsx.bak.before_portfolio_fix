import React from "react";
import { View, Text, ScrollView } from "react-native";
import Header from "@/components/Header";
import Badge from "@/components/Badge";
import Tile from "@/components/Tile";
import ActionTile from "@/components/ActionTile";
import PortfolioChart from "@/components/PortfolioChart";
import usePortfolioSeries from "../hooks/usePortfolioSeries";
import Card from "@/components/ui/Card";
import { space, color, text as T } from "../theme/tokens";

export default function Home() {
  const { series, current, deltaPct } = usePortfolioSeries();
  const deltaText = typeof deltaPct === "number" ? `${deltaPct >= 0 ? "+" : ""}${deltaPct.toFixed(1)}%` : "—";

  return (
    <ScrollView style={{ flex: 1, backgroundColor: color.bg }} contentContainerStyle={{ paddingBottom: space.xxl }}>
      <Header title="Your Portfolio" subtitle="Track • Value • Predict" />
      <View style={{ paddingHorizontal: space.lg, gap: space.lg, marginTop: space.sm }}>
        <Card>
          <View style={{ flexDirection:"row", alignItems:"center", justifyContent:"space-between" }}>
            <Text style={{ fontSize: T.xl, fontWeight:"800" }}>Portfolio</Text>
            <Badge variant={typeof deltaPct === "number" && deltaPct >= 0 ? "success" : "danger"}>{deltaText}</Badge>
          </View>
          <Text style={{ color: color.textMuted, marginTop: 4 }}>
            Current value{current != null ? `: ${current}` : ""}
          </Text>
          <View style={{ marginTop: space.md }}>
            <PortfolioChart data={series} width={340} height={120} />
          </View>
        </Card>

        <View style={{ gap: space.sm }}>
	  <ActionTile title="Add Item" subtitle="Add to your collection" href="/portfolio" />
	  <ActionTile title="Browse Marketplace" subtitle="See latest listings" href="/marketplace/listings" />
	  <ActionTile title="Categories" subtitle="Explore by category" href="/categories" />
        </View>

        <Tile title="Spotlight" subtitle="Hand-picked items for you" />
      </View>
    </ScrollView>
  );
}
