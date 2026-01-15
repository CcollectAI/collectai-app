import React, { useMemo } from "react";
import { View, Text, ScrollView, Pressable } from "react-native";
import { useLocalSearchParams, Link, useRouter } from "expo-router";
import { useAppTheme } from "@/hooks/useAppTheme";

// Best-effort category lookup (optional)
let getCategoryById: any = null;
try {
  // If you have this in src/data/categories.ts, this will work.
  getCategoryById = require("@/data/categories").getCategoryById;
} catch {
  getCategoryById = null;
}

export default function CategoryOverviewScreen() {
  const router = useRouter();
  const { categoryId } = useLocalSearchParams<{ categoryId?: string }>();
  const { colors, spacing, radius } = useAppTheme();

  const cat = useMemo(() => {
    if (!categoryId) return null;
    try {
      return getCategoryById ? getCategoryById(String(categoryId)) : null;
    } catch {
      return null;
    }
  }, [categoryId]);

  const title = cat?.name ?? cat?.title ?? (categoryId ? String(categoryId) : "Category");

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={{ padding: spacing.md, gap: spacing.md }}>
        <Text style={{ fontSize: 22, fontWeight: "800", color: colors.text }}>
          {title}
        </Text>

        <View
          style={{
            backgroundColor: colors.card,
            borderRadius: radius.lg,
            borderWidth: 1,
            borderColor: colors.border,
            padding: spacing.md,
            gap: spacing.sm,
          }}
        >
          <Text style={{ color: colors.muted }}>
            This is the Category Overview route. It was missing, so navigation couldn’t reach it.
          </Text>

          <Text style={{ color: colors.text, fontWeight: "700" }}>Quick actions</Text>

          {/* Go to Items tab filtered by category (items.tsx already reads params) */}
          <Link
            href={{ pathname: "/(tabs)/items", params: { category: String(categoryId ?? "") } }}
            asChild
          >
            <Pressable
              style={{
                backgroundColor: colors.brand.base,
                paddingVertical: 12,
                paddingHorizontal: 14,
                borderRadius: radius.md,
              }}
            >
              <Text style={{ color: "#fff", fontWeight: "800" }}>View items in this category</Text>
            </Pressable>
          </Link>

          {/* Go to Category chat if present */}
          <Link
            href={{ pathname: "/chat/category/[categoryId]", params: { categoryId: String(categoryId ?? "") } }}
            asChild
          >
            <Pressable
              style={{
                backgroundColor: colors.card,
                borderWidth: 1,
                borderColor: colors.border,
                paddingVertical: 12,
                paddingHorizontal: 14,
                borderRadius: radius.md,
              }}
            >
              <Text style={{ color: colors.text, fontWeight: "800" }}>Open category chat</Text>
            </Pressable>
          </Link>

          {/* Back */}
          <Pressable
            onPress={() => router.back()}
            style={{
              alignSelf: "flex-start",
              paddingVertical: 10,
              paddingHorizontal: 12,
            }}
          >
            <Text style={{ color: colors.brand.dark, fontWeight: "800" }}>← Back</Text>
          </Pressable>
        </View>
      </ScrollView>
    </View>
  );
}
