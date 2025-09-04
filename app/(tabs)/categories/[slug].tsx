import React from "react";
import { useLocalSearchParams } from "expo-router";
import CategoryDetail from "../../../src/screens/CategoryDetail";

export default function CategorySlugRoute() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  if (!slug) return null;
  return <CategoryDetail slug={String(slug)} />;
}
