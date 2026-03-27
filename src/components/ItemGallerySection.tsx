/**
 * Image gallery section for item detail screen.
 *
 * Renders a horizontal paging FlatList of item photos with label badges,
 * counter badges, page dots, an "Add Photo" card for saved items,
 * single-image fallback for drafts, and photo error banners.
 *
 * Extracted from app/item/[id].tsx to reduce file size.
 */
import React, { useCallback, useState } from "react";
import {
  View,
  Text,
  FlatList,
  Pressable,
  ActivityIndicator,
  Alert,
  StyleSheet,
} from "react-native";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";
import { fireHaptic, HapticIntent } from "@/haptics";
import { Skeleton } from "@/components/Skeleton";
import { radius, gap, text as textToken, fontWeight as fw, shadow } from "@/theme/tokens";

// ── Exported types ──────────────────────────────────────────────────────

export type ItemImage = {
  id: string;
  item_id: string;
  image_url: string;
  label: string | null;
  position: number;
  created_at: string | null;
};

// ── Constants ───────────────────────────────────────────────────────────

const LABEL_DISPLAY: Record<string, string> = {
  front: "Front",
  back: "Back",
  detail: "Detail",
  box: "Box",
  certificate: "Certificate",
  damage: "Damage",
  other: "Other",
};

// ── Props interface ─────────────────────────────────────────────────────

interface ItemGallerySectionProps {
  theme: {
    text: string;
    muted: string;
    accent: string;
    accentText: string;
    border: string;
    background: string;
    card: string;
    danger?: string;
  };
  hapticsEnabled: boolean;
  galleryLoading: boolean;
  effectiveGalleryImages: ItemImage[];
  galleryActiveIndex: number;
  GALLERY_WIDTH: number;
  GALLERY_HEIGHT: number;
  galleryFlatListRef: React.RefObject<FlatList | null>;
  isDraft: boolean;
  id: string | undefined;
  isEditing: boolean;
  imageUploading: boolean;
  photoUploading: boolean;
  photoError: string | null;
  displayImageUri: string | null | undefined;
  editableName: string;
  showPhotoSourcePicker: () => void;
  onGalleryDelete: (imageId: string) => void;
  onZoomImage: (uri: string) => void;
  onMomentumScrollEnd: (index: number) => void;
}

// ── Component ───────────────────────────────────────────────────────────

export const ItemGallerySection = React.memo(function ItemGallerySection({
  theme,
  hapticsEnabled,
  galleryLoading,
  effectiveGalleryImages,
  galleryActiveIndex,
  GALLERY_WIDTH,
  GALLERY_HEIGHT,
  galleryFlatListRef,
  isDraft,
  id,
  isEditing,
  imageUploading,
  photoUploading,
  photoError,
  displayImageUri,
  editableName,
  showPhotoSourcePicker,
  onGalleryDelete,
  onZoomImage,
  onMomentumScrollEnd,
}: ItemGallerySectionProps) {
  const [failedImageIds, setFailedImageIds] = useState<Set<string>>(new Set());

  const handleImageError = useCallback((imageId: string) => {
    setFailedImageIds((prev) => {
      const next = new Set(prev);
      next.add(imageId);
      return next;
    });
  }, []);

  if (galleryLoading) {
    return (
      <View style={s.galleryContainer}>
        <Skeleton width={GALLERY_WIDTH} height={GALLERY_HEIGHT} borderRadius={16} />
      </View>
    );
  }

  if (effectiveGalleryImages.length > 0 || (!isDraft && id)) {
    // Build data array: real/effective images + "Add Photo" card for saved items
    const galleryData: Array<
      | ({ type: "image" } & ItemImage)
      | { type: "add"; id: string; item_id: string; image_url: string; label: null; position: number; created_at: null }
    > = [
      ...effectiveGalleryImages.map((img) => ({ type: "image" as const, ...img })),
      ...(!isDraft && id
        ? [{ type: "add" as const, id: "__add__", item_id: "", image_url: "", label: null as null, position: 999, created_at: null as null }]
        : []),
    ];
    const totalSlides = galleryData.length;
    const imageCount = effectiveGalleryImages.length;

    return (
      <View style={s.galleryContainer}>
        <FlatList
          ref={galleryFlatListRef}
          data={galleryData}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          removeClippedSubviews={true}
          keyExtractor={(item) => item.id}
          onMomentumScrollEnd={(e) => {
            const idx = Math.round(e.nativeEvent.contentOffset.x / GALLERY_WIDTH);
            onMomentumScrollEnd(idx);
          }}
          getItemLayout={(_data, index) => ({
            length: GALLERY_WIDTH,
            offset: GALLERY_WIDTH * index,
            index,
          })}
          renderItem={({ item, index }) => {
            if (item.type === "add") {
              return (
                <Pressable
                  onPress={showPhotoSourcePicker}
                  disabled={imageUploading || photoUploading}
                  style={[
                    s.gallerySlide,
                    { width: GALLERY_WIDTH, height: GALLERY_HEIGHT, borderColor: theme.border },
                  ]}
                  accessibilityRole="button"
                  accessibilityLabel="Add a new photo"
                  accessibilityHint="Double tap to open photo picker"
                >
                  <View style={[s.galleryAddCard, { backgroundColor: theme.card, borderColor: theme.accent }]}>
                    {imageUploading || photoUploading ? (
                      <ActivityIndicator size="large" color={theme.accent} />
                    ) : (
                      <>
                        <Ionicons name="camera-outline" size={36} color={theme.accent} />
                        <Text style={[s.galleryAddText, { color: theme.accent }]}>Add Photo</Text>
                      </>
                    )}
                  </View>
                </Pressable>
              );
            }
            // Normal image slide
            const isRealGalleryImage = item.id !== "__original__";
            return (
              <View style={[s.gallerySlide, { width: GALLERY_WIDTH, height: GALLERY_HEIGHT }]}>
                <Pressable
                  onPress={() => onZoomImage(item.image_url)}
                  accessibilityRole="button"
                  accessibilityLabel={`Photo ${index + 1} of ${imageCount}${item.label ? ` (${LABEL_DISPLAY[item.label] || item.label})` : ""}`}
                  accessibilityHint="Double tap to zoom in on this photo"
                >
                  {failedImageIds.has(item.id) ? (
                    <View style={[s.galleryFallback, { width: GALLERY_WIDTH, height: GALLERY_HEIGHT, backgroundColor: theme.background }]}>
                      <Ionicons name="image-outline" size={48} color={theme.muted} />
                      <Text style={[s.galleryFallbackText, { color: theme.muted }]}>Image unavailable</Text>
                    </View>
                  ) : (
                    <Image
                      source={{ uri: item.image_url }}
                      placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
                      style={{ width: GALLERY_WIDTH, height: GALLERY_HEIGHT }}
                      contentFit="cover"
                      cachePolicy="memory-disk"
                      transition={200}
                      onError={() => handleImageError(item.id)}
                    />
                  )}
                </Pressable>
                {/* Label badge — bottom-left */}
                {item.label && (
                  <View style={[s.galleryLabelBadge, { backgroundColor: theme.accent }]}>
                    <Text style={[s.galleryLabelText, { color: theme.accentText }]}>
                      {LABEL_DISPLAY[item.label] || item.label}
                    </Text>
                  </View>
                )}
                {/* Counter badge — bottom-right (only when multiple images) */}
                {imageCount > 1 && (
                  <View style={s.galleryCounterBadge}>
                    <Text style={[s.galleryCounterText, { color: theme.accentText }]}>
                      {index + 1}/{imageCount}
                    </Text>
                  </View>
                )}
                {/* Delete button in edit mode — only for real gallery images */}
                {isEditing && isRealGalleryImage && (
                  <Pressable
                    onPress={() => {
                      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: hapticsEnabled });
                      Alert.alert(
                        "Delete Photo",
                        "Are you sure you want to remove this photo?",
                        [
                          { text: "Cancel", style: "cancel" },
                          {
                            text: "Delete",
                            style: "destructive",
                            onPress: () => onGalleryDelete(item.id),
                          },
                        ],
                      );
                    }}
                    style={[s.galleryDeleteBtn, { backgroundColor: theme.card + "D9" }]}
                    accessibilityRole="button"
                    accessibilityLabel="Delete this photo"
                    accessibilityHint="Double tap to remove this photo from the gallery"
                  >
                    <Ionicons name="close-circle" size={26} color={theme.danger ?? "#EF4444"} />
                  </Pressable>
                )}
              </View>
            );
          }}
        />
        {/* Page dots */}
        {totalSlides > 1 && (
          <View style={s.galleryDots}>
            {galleryData.map((img, idx) => (
              <View
                key={img.id}
                style={[
                  s.galleryDot,
                  {
                    backgroundColor: idx === galleryActiveIndex
                      ? theme.accent
                      : theme.border,
                  },
                ]}
              />
            ))}
          </View>
        )}
        {/* Photo error */}
        {photoError && (
          <View style={s.photoErrorBanner}>
            <Text style={s.photoErrorText}>{photoError}</Text>
          </View>
        )}
      </View>
    );
  }

  // Fallback: single image (draft mode or no images at all)
  return (
    <View style={[s.imageWrapper, { borderColor: theme.border }]}>
      <Pressable
        onPress={() => {
          if (displayImageUri) {
            onZoomImage(displayImageUri);
          }
        }}
        accessibilityRole="button"
        accessibilityLabel="Item photo"
        accessibilityHint="Double tap to zoom in on this photo"
      >
        {displayImageUri && !failedImageIds.has("__single__") ? (
          <Image
            source={{ uri: displayImageUri }}
            placeholder={{ blurhash: 'L6PZfSi_.AyE_3t7t7R**0o#DgR4' }}
            style={s.image}
            contentFit="cover"
            cachePolicy="memory-disk"
            transition={200}
            accessibilityRole="image"
            accessibilityLabel={`Photo of ${editableName}`}
            onError={() => handleImageError("__single__")}
          />
        ) : (
          <Image
            source={require("../../assets/placeholder.png")}
            style={s.image}
            contentFit="cover"
            accessibilityRole="image"
            accessibilityLabel={`Placeholder image for ${editableName}`}
          />
        )}
      </Pressable>

      {/* Photo upload overlay button */}
      <Pressable
        onPress={showPhotoSourcePicker}
        disabled={photoUploading}
        style={[
          s.photoUploadOverlay,
          !displayImageUri && s.photoUploadOverlayEmpty,
        ]}
        accessibilityRole="button"
        accessibilityLabel={displayImageUri ? "Change photo" : "Add your photo"}
        accessibilityHint="Double tap to open photo picker"
      >
        {photoUploading ? (
          <ActivityIndicator size="small" color={theme.accentText} />
        ) : (
          <>
            <Ionicons
              name={displayImageUri ? "camera" : "camera-outline"}
              size={displayImageUri ? 18 : 28}
              color={theme.accentText}
            />
            {!displayImageUri && (
              <Text style={[s.photoUploadOverlayText, { color: theme.accentText }]}>
                Add your photo
              </Text>
            )}
          </>
        )}
      </Pressable>

      {/* Photo error */}
      {photoError && (
        <View style={s.photoErrorBanner}>
          <Text style={s.photoErrorText}>{photoError}</Text>
        </View>
      )}
    </View>
  );
});

// ── Styles ──────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  galleryContainer: {
    width: "100%",
    marginBottom: 16,
    borderRadius: radius.md,
    overflow: "hidden",
  },
  gallerySlide: {
    borderRadius: radius.md,
    overflow: "hidden",
  },
  galleryAddCard: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    borderRadius: radius.md,
    borderWidth: 2,
    borderStyle: "dashed",
    borderColor: undefined,
  },
  galleryAddText: {
    fontSize: textToken.lg,
    fontWeight: fw.semibold,
  },
  galleryLabelBadge: {
    position: "absolute",
    bottom: 10,
    left: 10,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radius.md,
  },
  galleryLabelText: {
    fontSize: textToken.sm,
    fontWeight: fw.bold,
    textTransform: "capitalize",
  },
  galleryDeleteBtn: {
    position: "absolute",
    top: 8,
    right: 8,
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
  },
  galleryCounterBadge: {
    position: "absolute",
    bottom: 10,
    right: 10,
    backgroundColor: "rgba(0,0,0,0.55)",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.sm,
  },
  galleryCounterText: {
    fontSize: textToken.sm,
    fontWeight: fw.semibold,
  },
  galleryDots: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: gap.sm,
    paddingVertical: 10,
  },
  galleryDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  galleryFallback: {
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  galleryFallbackText: {
    fontSize: textToken.md,
    fontWeight: fw.medium,
  },
  imageWrapper: {
    width: "100%",
    height: 260,
    borderRadius: radius.md,
    borderWidth: 1,
    overflow: "hidden",
    marginBottom: 16,
  },
  image: {
    width: "100%",
    height: "100%",
  },
  photoUploadOverlay: {
    position: "absolute",
    bottom: 12,
    right: 12,
    backgroundColor: "rgba(0,0,0,0.55)",
    borderRadius: radius.lg,
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  photoUploadOverlayEmpty: {
    bottom: 0,
    right: 0,
    left: 0,
    top: 0,
    width: "100%",
    height: "100%",
    borderRadius: 0,
    backgroundColor: "rgba(0,0,0,0.15)",
    gap: 8,
  },
  photoUploadOverlayText: {
    fontSize: textToken.lg,
    fontWeight: fw.semibold,
  },
  photoErrorBanner: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: "rgba(220,38,38,0.85)",
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  photoErrorText: {
    color: "#FFFFFF",
    fontSize: textToken.sm,
    textAlign: "center",
  },
});
