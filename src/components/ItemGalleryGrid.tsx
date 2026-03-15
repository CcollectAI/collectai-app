/**
 * ItemGalleryGrid - Pinterest-style image grid for collection items.
 * Provides a visual gallery view with tap to expand functionality.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Modal,
  useWindowDimensions,
} from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import { formatPrice } from '@/lib/format';

interface GalleryItem {
  id: string;
  name: string;
  category: string;
  value: number;
  imageUrl?: string;
}

interface Props {
  items: GalleryItem[];
  onItemPress?: (item: GalleryItem) => void;
  numColumns?: number;
  colors: {
    card: string;
    text: string;
    muted: string;
    border: string;
    accent: string;
  };
}

const PLACEHOLDER_IMAGE = require('../../assets/placeholder.png');

// Default blurhash for smooth image loading (neutral gray gradient)
const DEFAULT_BLURHASH = 'L6PZfSi_.AyE_3t7t7R**0o#DgR4';

export function ItemGalleryGrid({
  items,
  onItemPress,
  numColumns = 2,
  colors,
}: Props) {
  const { width } = useWindowDimensions();
  const [selectedItem, setSelectedItem] = useState<GalleryItem | null>(null);
  const [lightboxVisible, setLightboxVisible] = useState(false);

  const itemWidth = (width - 48 - (numColumns - 1) * 12) / numColumns;
  const itemHeight = itemWidth * 1.2;

  const handleItemPress = (item: GalleryItem) => {
    if (onItemPress) {
      onItemPress(item);
    } else {
      setSelectedItem(item);
      setLightboxVisible(true);
    }
  };

  const closeLightbox = () => {
    setLightboxVisible(false);
    setSelectedItem(null);
  };

  const renderLightbox = () => {
    if (!selectedItem) return null;

    return (
      <Modal
        visible={lightboxVisible}
        transparent
        animationType="fade"
        onRequestClose={closeLightbox}
      >
        <Pressable style={styles.lightboxOverlay} onPress={closeLightbox} accessibilityRole="button" accessibilityLabel="Close lightbox">
          <View style={styles.lightboxContent}>
            <Pressable style={styles.closeButton} onPress={closeLightbox} accessibilityRole="button" accessibilityLabel="Close image viewer">
              <Ionicons name="close" size={28} color="#fff" />
            </Pressable>

            {selectedItem.imageUrl ? (
              <Image
                source={{ uri: selectedItem.imageUrl }}
                placeholder={{ blurhash: DEFAULT_BLURHASH }}
                style={styles.lightboxImage}
                contentFit="contain"
                cachePolicy="memory-disk"
                transition={200}
              />
            ) : (
              <View style={[styles.lightboxPlaceholder, { backgroundColor: colors.border }]}>
                <Ionicons name="image-outline" size={64} color={colors.muted} />
              </View>
            )}

            <View style={styles.lightboxInfo}>
              <Text style={styles.lightboxName}>{selectedItem.name}</Text>
              <Text style={styles.lightboxCategory}>{selectedItem.category}</Text>
              <Text style={styles.lightboxPrice}>
                {formatPrice(selectedItem.value)}
              </Text>
            </View>
          </View>
        </Pressable>
      </Modal>
    );
  };

  if (items.length === 0) {
    return (
      <View style={styles.emptyContainer}>
        <Ionicons name="images-outline" size={48} color={colors.muted} />
        <Text style={[styles.emptyText, { color: colors.muted }]}>
          No items to display
        </Text>
      </View>
    );
  }

  // Group items into rows for grid layout
  const rows: GalleryItem[][] = [];
  for (let i = 0; i < items.length; i += numColumns) {
    rows.push(items.slice(i, i + numColumns));
  }

  return (
    <View style={styles.container}>
      <View style={styles.gridContainer}>
        {rows.map((row, rowIndex) => (
          <View key={`row-${rowIndex}`} style={styles.row}>
            {row.map((item, colIndex) => (
              <Pressable
                key={item.id}
                style={[
                  styles.gridItem,
                  {
                    width: itemWidth,
                    height: itemHeight,
                    backgroundColor: colors.card,
                    borderColor: colors.border,
                    marginLeft: colIndex === 0 ? 0 : 12,
                  },
                ]}
                onPress={() => handleItemPress(item)}
                accessibilityRole="button"
                accessibilityLabel={`${item.name}, ${item.category}, ${formatPrice(item.value)}`}
              >
                {item.imageUrl ? (
                  <Image
                    source={{ uri: item.imageUrl }}
                    placeholder={{ blurhash: DEFAULT_BLURHASH }}
                    style={styles.itemImage}
                    contentFit="cover"
                    cachePolicy="memory-disk"
                    transition={200}
                  />
                ) : (
                  <View style={[styles.placeholderContainer, { backgroundColor: colors.border }]}>
                    <Ionicons name="image-outline" size={32} color={colors.muted} />
                  </View>
                )}

                <View style={[styles.itemOverlay, { backgroundColor: 'rgba(0,0,0,0.5)' }]}>
                  <Text style={styles.itemName} numberOfLines={2}>
                    {item.name}
                  </Text>
                  <Text style={styles.itemPrice}>{formatPrice(item.value)}</Text>
                </View>

                <View style={[styles.categoryBadge, { backgroundColor: colors.accent }]}>
                  <Text style={styles.categoryText} numberOfLines={1}>
                    {item.category}
                  </Text>
                </View>
              </Pressable>
            ))}
            {/* Fill empty slots in the last row */}
            {row.length < numColumns &&
              Array.from({ length: numColumns - row.length }).map((_, i) => (
                <View
                  key={`empty-${i}`}
                  style={{ width: itemWidth, marginLeft: 12 }}
                />
              ))}
          </View>
        ))}
      </View>
      {renderLightbox()}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  gridContainer: {
    paddingVertical: 12,
  },
  row: {
    flexDirection: 'row',
    marginBottom: 12,
  },
  gridItem: {
    borderRadius: 12,
    borderWidth: 1,
    overflow: 'hidden',
    position: 'relative',
  },
  itemImage: {
    width: '100%',
    height: '100%',
  },
  placeholderContainer: {
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  itemOverlay: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: 10,
  },
  itemName: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 2,
  },
  itemPrice: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '700',
  },
  categoryBadge: {
    position: 'absolute',
    top: 8,
    left: 8,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
  },
  categoryText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '600',
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    marginTop: 12,
    fontSize: 14,
  },
  // Lightbox styles
  lightboxOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.9)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  lightboxContent: {
    width: '90%',
    maxHeight: '85%',
    alignItems: 'center',
  },
  closeButton: {
    position: 'absolute',
    top: -40,
    right: 0,
    padding: 8,
    zIndex: 10,
  },
  lightboxImage: {
    width: '100%',
    height: 350,
    borderRadius: 12,
  },
  lightboxPlaceholder: {
    width: '100%',
    height: 350,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  lightboxInfo: {
    marginTop: 20,
    alignItems: 'center',
  },
  lightboxName: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
    textAlign: 'center',
  },
  lightboxCategory: {
    color: '#9ca3af',
    fontSize: 14,
    marginTop: 4,
  },
  lightboxPrice: {
    color: '#81D8D0',
    fontSize: 22,
    fontWeight: '700',
    marginTop: 8,
  },
});

export default ItemGalleryGrid;
