import React from "react";
import { View, Text, Pressable } from "react-native";
import { Link, useRouter } from "expo-router";

type Props = {
  title: string;
  subtitle?: string;
  href?: string;                 // use this to navigate with Expo Router
  onPress?: () => void;          // fallback action if no href
  left?: React.ReactNode;        // optional icon/avatar on the left
  right?: React.ReactNode;       // optional element on the right (badge, chevron, etc.)
  disabled?: boolean;
  testID?: string;
};

export default function ActionTile({
  title,
  subtitle,
  href,
  onPress,
  left,
  right,
  disabled,
  testID,
}: Props) {
  const router = useRouter();

  const content = (
    <View
      style={{
        padding: 14,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: "#e5e7eb",
        backgroundColor: disabled ? "#f9fafb" : "#ffffff",
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
      }}
    >
      {left ? <View style={{ width: 28, alignItems: "center" }}>{left}</View> : null}

      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 16, fontWeight: "600" }}>{title}</Text>
        {subtitle ? (
          <Text style={{ color: "#6b7280", marginTop: 2 }}>{subtitle}</Text>
        ) : null}
      </View>

      {right ? <View style={{ marginLeft: 8 }}>{right}</View> : null}
    </View>
  );

  if (href && !disabled) {
    // Link preserves web accessibility & native navigation
    return (
      <Link
        href={href}
        asChild
        testID={testID}
        // NOTE: Link handles press internally when asChild is used
      >
        <Pressable accessibilityRole="button">{content}</Pressable>
      </Link>
    );
  }

  return (
    <Pressable
      onPress={() => {
        if (disabled) return;
        if (onPress) return onPress();
        // graceful fallback: if no onPress but href exists
        if (href) router.push(href);
      }}
      disabled={disabled}
      accessibilityRole="button"
      testID={testID}
    >
      {content}
    </Pressable>
  );
}
