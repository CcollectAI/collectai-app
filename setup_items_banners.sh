#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

mkdir -p src/components

# 1) Calendar banner (for portfolio + items)
cat > src/components/UpcomingEventsBanner.tsx <<'TSX'
import React from "react";
import { View, Text, Pressable } from "react-native";
import { useRouter } from "expo-router";

type BannerContext = "portfolio" | "items";

interface Props {
  context?: BannerContext;
}

/**
 * CTA banner for upcoming events & drops (calendar).
 */
export default function UpcomingEventsBanner({ context = "portfolio" }: Props) {
  const router = useRouter();

  const title =
    context === "items"
      ? "Events & drops for your items"
      : "Upcoming events & drops";

  const subtitle =
    context === "items"
      ? "See events and release dates relevant to your collection."
      : "Track big releases, tournaments, and value catalysts.";

  const buttonLabel =
    context === "items" ? "Open events calendar" : "View events calendar";

  return (
    <View
      style={{
        marginTop: 16,
        marginBottom: 16,
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

      <Pressable
        onPress={() => router.push("/calendar-v1-demo")}
        style={{
          alignSelf: "flex-start",
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
          {buttonLabel}
        </Text>
      </Pressable>
    </View>
  );
}
TSX

# 2) Build & paint projects banner (items only, bottom of screen)
cat > src/components/BuildProjectsBanner.tsx <<'TSX'
import React from "react";
import { View, Text, Pressable } from "react-native";
import { useRouter } from "expo-router";

/**
 * CTA banner for build & paint projects (Gunpla, minis, customs).
 */
export default function BuildProjectsBanner() {
  const router = useRouter();

  return (
    <View
      style={{
        marginTop: 8,
        marginBottom: 24,
        padding: 16,
        borderRadius: 12,
        backgroundColor: "#F7F2FF",
        borderWidth: 1,
        borderColor: "#D6C4F5",
      }}
    >
      <Text
        style={{
          fontSize: 14,
          fontWeight: "600",
          marginBottom: 4,
        }}
      >
        Build & paint projects
      </Text>
      <Text
        style={{
          fontSize: 12,
          marginBottom: 12,
          opacity: 0.85,
        }}
      >
        Track in-progress builds, paint queues, and kits that haven&apos;t hit
        your main portfolio yet.
      </Text>

      <Pressable
        // TODO: update this route to your real build/paint projects screen
        onPress={() => router.push("/build-paint-projects")}
        style={{
          alignSelf: "flex-start",
          paddingHorizontal: 14,
          paddingVertical: 8,
          borderRadius: 999,
          backgroundColor: "#7C5CFF",
        }}
      >
        <Text
          style={{
            color: "#FFFFFF",
            fontSize: 12,
            fontWeight: "600",
          }}
        >
          Open build & paint view
        </Text>
      </Pressable>
    </View>
  );
}
TSX

# 3) Items overview banner (top of items screen)
cat > src/components/ItemsOverviewBanner.tsx <<'TSX'
import React from "react";
import { View, Text } from "react-native";

/**
 * Top-of-screen banner on Items to visually frame the portfolio total
 * and list below. Uses same style as the other banners.
 *
 * NOTE: It does NOT move existing total into the banner automatically,
 * but sits directly above it to make that section pop more.
 */
export default function ItemsOverviewBanner() {
  return (
    <View
      style={{
        marginBottom: 12,
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
        Collection items overview
      </Text>
      <Text
        style={{
          fontSize: 12,
          opacity: 0.85,
        }}
      >
        Your portfolio total and item breakdown are shown just below. Use this
        view to drill into categories, value, and individual pieces.
      </Text>
    </View>
  );
}
TSX

echo "✅ Created / updated banners:"
echo "  - src/components/UpcomingEventsBanner.tsx"
echo "  - src/components/BuildProjectsBanner.tsx"
echo "  - src/components/ItemsOverviewBanner.tsx"
