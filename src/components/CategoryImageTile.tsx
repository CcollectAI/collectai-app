import React, { memo } from "react";
import { View, Text, StyleSheet } from "react-native";
import { Image, ImageSource } from "expo-image";
import { useAppTheme } from "@/hooks/useAppTheme";

type Props = {
  label: string;
  image: ImageSource;
  subtitle?: string;
};

const CategoryImageTileInner: React.FC<Props> = ({ label, image, subtitle }) => {
  const { colors: themeColors } = useAppTheme();
  const theme = {
    colors: {
      card: themeColors.card,
      text: themeColors.text,
      muted: themeColors.muted,
      primary: themeColors.accent,
    },
  };

  return (
    <View
      style={[
        styles.card,
        {
          backgroundColor: theme.colors.card,
        },
      ]}
    >
      <Image source={image} style={styles.image} contentFit="cover" cachePolicy="disk" transition={200} accessibilityLabel={`${label} category image`} />
      <View style={styles.textWrap}>
        <Text
          numberOfLines={1}
          style={[
            styles.label,
            {
              color: theme.colors.text,
            },
          ]}
        >
          {label}
        </Text>
        {!!subtitle && (
          <Text
            numberOfLines={1}
            style={[
              styles.subtitle,
              {
                color: theme.colors.muted,
              },
            ]}
          >
            {subtitle}
          </Text>
        )}
      </View>
    </View>
  );
};
export const CategoryImageTile = memo(CategoryImageTileInner);

const styles = StyleSheet.create({
  card: {
    width: 140,
    borderRadius: 12,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
    marginRight: 12,
  },
  image: {
    width: "100%",
    height: 90,
  },
  textWrap: {
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  label: {
    fontSize: 14,
    fontWeight: "600",
  },
  subtitle: {
    marginTop: 2,
    fontSize: 11,
  },
});