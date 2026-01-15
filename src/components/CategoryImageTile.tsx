import React from "react";
import { View, Text, Image, Pressable, StyleSheet, ImageSourcePropType } from "react-native";

type Props = {
  label: string;
  subtitle?: string;
  image?: ImageSourcePropType;
  onPress?: () => void;
};

const THEME = {
  BG: "#E6FFFA",
  CARD: "#FFFFFF",
  BORDER: "rgba(12,34,51,0.10)",
  NAVY: "#0C2233",
  MUTED: "rgba(12,34,51,0.62)",
  ACCENT_SOFT: "rgba(56,214,199,0.18)",
};

export function CategoryImageTile({ label, subtitle, image, onPress }: Props) {
  const Inner = (
    <View style={styles.card}>
      <View style={styles.row}>
        <View style={styles.thumb}>
          {image ? (
            <Image source={image} style={styles.img} resizeMode="cover" />
          ) : (
            <View style={styles.fallbackDot} />
          )}
        </View>

        <View style={{ flex: 1 }}>
          <Text style={styles.title} numberOfLines={1}>
            {label}
          </Text>
          {!!subtitle && (
            <Text style={styles.sub} numberOfLines={2}>
              {subtitle}
            </Text>
          )}
        </View>
      </View>
    </View>
  );

  if (onPress) {
    return (
      <Pressable accessibilityRole="button" onPress={onPress} style={{ alignSelf: "stretch" }}>
        {Inner}
      </Pressable>
    );
  }

  return Inner;
}

export default CategoryImageTile;

const styles = StyleSheet.create({
  card: {
    backgroundColor: THEME.CARD,
    borderWidth: 1,
    borderColor: THEME.BORDER,
    borderRadius: 16,
    padding: 12,
  },
  row: { flexDirection: "row", alignItems: "center", gap: 12 },
  thumb: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: THEME.ACCENT_SOFT,
    borderWidth: 1,
    borderColor: THEME.BORDER,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  img: { width: "100%", height: "100%" },
  fallbackDot: {
    width: 12,
    height: 12,
    borderRadius: 999,
    backgroundColor: THEME.NAVY,
    opacity: 0.25,
  },
  title: { fontSize: 14, fontWeight: "900", color: THEME.NAVY },
  sub: { marginTop: 2, fontWeight: "700", color: THEME.MUTED },
});
