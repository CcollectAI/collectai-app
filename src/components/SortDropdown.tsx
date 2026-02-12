import React from "react";
import { View, Text } from "react-native";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";

export type SortOption = "value_desc" | "value_asc" | "az" | "za";

interface Props {
  value: SortOption;
  onChange: (v: SortOption) => void;
}

export default function SortDropdown({ value, onChange }: Props) {
  const { settings } = useSettings();
  const opts: { label: string; v: SortOption }[] = [
    { label: "Value high → low", v: "value_desc" },
    { label: "Value low → high", v: "value_asc" },
    { label: "A → Z", v: "az" },
    { label: "Z → A", v: "za" },
  ];

  return (
    <View style={{ marginBottom: 12 }}>
      {opts.map((o) => (
        <AnimatedPressable
          key={o.v}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            onChange(o.v);
          }}
          accessibilityRole="button"
          accessibilityLabel={`Sort by ${o.label}${value === o.v ? ', selected' : ''}`}
          style={{
            paddingVertical: 6,
            paddingHorizontal: 8,
            backgroundColor: value === o.v ? "#E6F2FF" : "white",
            borderRadius: 6,
            marginBottom: 4,
          }}
        >
          <Text style={{ fontSize: 14 }}>{o.label}</Text>
        </AnimatedPressable>
      ))}
    </View>
  );
}
