#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

BANNER_FILE="src/components/UpcomingEventsBanner.tsx"

mkdir -p "src/components"

cat > "$BANNER_FILE" <<'TSX'
import React from "react";
import { View, Text, Pressable } from "react-native";
import { useRouter } from "expo-router";

type BannerContext = "portfolio" | "items";

interface Props {
  context?: BannerContext;
}

/**
 * CTA banner for:
 *  - Portfolio: upcoming events & drops (calendar)
 *  - Items: calendar + build/paint projects entry
 */
export default function UpcomingEventsBanner({ context = "portfolio" }: Props) {
  const router = useRouter();

  const isItems = context === "items";

  const title = isItems
    ? "Your items & build backlog"
    : "Upcoming events & drops";

  const subtitle = isItems
    ? "See events for your collection and jump into build/paint projects."
    : "Track big releases, tournaments, and value catalysts for your collection.";

  const primaryLabel = isItems ? "Open events calendar" : "View events calendar";

  return (
    <View
      style={{
        marginTop: 16,
        marginBottom: 24,
        padding: 16,
        borderRadius: 12,
        backgroundColor: "#E5F4F8",
        borderWidth: 1,
        borderColor: "#B4DDE7",
      }}
    >
      <Text
        style={{
          fontSize: 14,
          fontWeight: "600",
          marginBottom: 4,
        }}
      >
        {title}
      </Text>
      <Text
        style={{
          fontSize: 12,
          marginBottom: 12,
          opacity: 0.85,
        }}
      >
        {subtitle}
      </Text>

      <View
        style={{
          flexDirection: "row",
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <Pressable
          onPress={() => router.push("/calendar-v1-demo")}
          style={{
            paddingHorizontal: 14,
            paddingVertical: 8,
            borderRadius: 999,
            backgroundColor: "#00A3C4",
          }}
        >
          <Text
            style={{
              color: "#FFFFFF",
              fontSize: 12,
              fontWeight: "600",
            }}
          >
            {primaryLabel}
          </Text>
        </Pressable>

        {isItems && (
          <Pressable
            // TODO: adjust to your real route for build/paint projects
            onPress={() => router.push("/build-paint-projects")}
            style={{
              paddingHorizontal: 12,
              paddingVertical: 8,
              borderRadius: 999,
              backgroundColor: "#FFFFFF",
              borderWidth: 1,
              borderColor: "#B4DDE7",
            }}
          >
            <Text
              style={{
                fontSize: 12,
                fontWeight: "500",
                color: "#00546A",
              }}
            >
              Build & paint projects
            </Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}
TSX

echo "✅ Updated $BANNER_FILE"
