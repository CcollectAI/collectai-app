import React from "react";
import { View, Text, Pressable, ViewStyle } from "react-native";
import { Link, useRouter } from "expo-router";

type Props = {
  title: string;
  subtitle?: string;
  href?: string;                 // navigate to a route
  onPress?: () => void;          // or run a handler
  left?: React.ReactNode;        // optional icon/avatar on the left
  right?: React.ReactNode;       // optional right adornment (badge/chevron)
  style?: ViewStyle;             // extra container styles
  disabled?: boolean;
  testID?: string;
};

export default function Tile({
  title,
  subtitle,
  href,
  onPress,
  left,
  right,
  style,
  disabled,
  testID,
}: Props) {
  const router = useRouter();

  const inner = (
    <View
      style={[
        {
          padding: 16,
          borderRadius: 14,
          borderWidth: 1,
          borderColor: "#e5e7eb",
          backgroundColor: disabled ? "#f9fafb" : "#ffffff",
          gap: 10,
        },
        style,
      ]}
    >
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
          {left ? <View style={{ width: 28, alignItems: "center" }}>{left}</View> : null}
          <Text style={{ fontSize: 17, fontWeight: "700" }}>{title}</Text>
        </View>
        {right ? <View>{right}</View> : null}
      </View>
      {subtitle ? <Text style={{ color: "#6b7280" }}>{subtitle}</Text> : null}
    </View>
  );

  if (href && !disabled) {
    return (
      <Link href={href} asChild testID={testID}>
        <Pressable accessibilityRole="button">{inner}</Pressable>
      </Link>
    );
  }

  return (
    <Pressable
      onPress={() => {
        if (disabled) return;
        if (onPress) return onPress();
        if (href) router.push(href);
      }}
      disabled={disabled}
      accessibilityRole="button"
      testID={testID}
    >
      {inner}
    </Pressable>
  );
}
