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
        onPress={() => router.push("/calendar-v1-demo" as any)}
        accessibilityRole="button"
        accessibilityLabel={buttonLabel}
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
