/**
 * CatalogImage — remote catalog image with null + error fallback.
 *
 * Renders the reference photo for a `category_items.image_url`. When the URL
 * is null, empty, or fails to load (404, CDN rot, network error), it renders
 * an identical-sized placeholder with a category-themed icon instead of a
 * blank frame.
 *
 * Use this wherever `category_items.image_url` or `CatalogAlternative.imageUrl`
 * is rendered — ScanResultCard alternatives, CatalogBrowseSection, catalog
 * search results.
 */

import React, { useState, useMemo } from 'react';
import { View, StyleSheet, ImageResizeMode, StyleProp, ViewStyle, ImageStyle } from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';

type IconName = keyof typeof Ionicons.glyphMap;

interface CatalogImageProps {
  /** Catalog image URL (may be null/empty) */
  uri: string | null | undefined;
  /** Fixed size (or provide width/height via style) */
  size?: number;
  /** Placeholder icon when image is null/broken */
  fallbackIcon?: IconName;
  /** Background color for the placeholder box */
  fallbackBackground?: string;
  /** Icon color for the placeholder */
  fallbackIconColor?: string;
  /** Style override (accepts View or Image styles — both components use the same props) */
  style?: StyleProp<ViewStyle | ImageStyle>;
  /** resizeMode (defaults to 'cover') */
  resizeMode?: ImageResizeMode;
  /** Accessibility label */
  accessibilityLabel?: string;
}

export function CatalogImage({
  uri,
  size,
  fallbackIcon = 'cube-outline',
  fallbackBackground,
  fallbackIconColor,
  style,
  resizeMode = 'cover',
  accessibilityLabel,
}: CatalogImageProps) {
  const { colors } = useAppTheme();
  const [hasError, setHasError] = useState(false);

  // Reset error state when URI changes (e.g., user scrolls, new alternatives)
  const key = uri ?? 'null';
  const shouldShowFallback = !uri || hasError;

  const sizeStyle = useMemo(
    () => (size ? { width: size, height: size } : null),
    [size],
  );

  if (shouldShowFallback) {
    return (
      <View
        style={[
          styles.placeholder,
          sizeStyle,
          { backgroundColor: fallbackBackground ?? colors.skeleton },
          style as StyleProp<ViewStyle>,
        ]}
        accessibilityLabel={accessibilityLabel ?? 'No image available'}
        accessibilityRole="image"
      >
        <Ionicons
          name={fallbackIcon}
          size={size ? Math.max(16, size * 0.4) : 20}
          color={fallbackIconColor ?? colors.muted}
        />
      </View>
    );
  }

  return (
    <Image
      key={key}
      source={{ uri: uri ?? '' }}
      style={[sizeStyle, style] as StyleProp<ImageStyle>}
      contentFit={resizeMode === 'cover' ? 'cover' : 'contain'}
      accessibilityLabel={accessibilityLabel}
      onError={() => setHasError(true)}
      transition={150}
    />
  );
}

const styles = StyleSheet.create({
  placeholder: {
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
});
