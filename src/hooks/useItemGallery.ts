/**
 * useItemGallery — manages multi-photo gallery state for the item detail screen.
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import type { FlatList } from 'react-native';
import { collectorsApi } from '@/api/collectorsApi';
import { usePhotoUpload } from '@/hooks/usePhotoUpload';
import { showActionSheet } from '@/hooks/useActionSheetPicker';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useToast } from '@/components/Toast';
import { useSettings } from '@/lib/settings';
import logger from '@/utils/logger';
import type { ItemImage } from '@/components/ItemGallerySection';

const IMAGE_LABELS = ['front', 'back', 'detail', 'box', 'certificate', 'damage', 'other'] as const;
const LABEL_DISPLAY: Record<string, string> = {
  front: 'Front', back: 'Back', detail: 'Detail', box: 'Box',
  certificate: 'Certificate', damage: 'Damage', other: 'Other',
};

export function useItemGallery(itemId: string | undefined, isDraft: boolean, imageUri?: string) {
  const { settings } = useSettings();
  const { showToast } = useToast();
  const { pickAndUpload, uploading: photoUploading, error: photoError, photoUrl: userPhotoUrl } = usePhotoUpload(itemId || 'draft');

  const [userPhoto, setUserPhoto] = useState<string | null>(null);
  const [zoomVisible, setZoomVisible] = useState(false);
  const [zoomImageUri, setZoomImageUri] = useState<string | null>(null);
  const [galleryImages, setGalleryImages] = useState<ItemImage[]>([]);
  const [galleryLoading, setGalleryLoading] = useState(false);
  const [galleryError, setGalleryError] = useState<Error | null>(null);
  const [galleryActiveIndex, setGalleryActiveIndex] = useState(0);
  const [imageUploading, setImageUploading] = useState(false);
  const [pendingLabel, setPendingLabel] = useState<string | null>(null);
  const flatListRef = useRef<FlatList>(null);

  const displayImageUri = galleryImages.length > 0
    ? galleryImages[0].image_url
    : (userPhoto || userPhotoUrl || imageUri);

  const effectiveGalleryImages = useMemo((): ItemImage[] => {
    if (galleryImages.length > 0) return galleryImages;
    const fallbackUri = userPhoto || userPhotoUrl || imageUri;
    if (fallbackUri) {
      return [{ id: '__original__', item_id: itemId || '', image_url: fallbackUri, label: null, position: 0, created_at: null }];
    }
    return [];
  }, [galleryImages, userPhoto, userPhotoUrl, imageUri, itemId]);

  useEffect(() => {
    if (!itemId || isDraft) return;
    let cancelled = false;
    setGalleryLoading(true);
    setGalleryError(null);
    collectorsApi.listItemImages(itemId)
      .then((data) => { if (!cancelled) setGalleryImages(data.images || []); })
      .catch((err) => {
        logger.warn('[useItemGallery] fetch error:', err);
        // Round-4 silent-failure sweep: previously err was logged only,
        // leaving galleryImages=[] indistinguishable from "legitimately
        // no photos." Now callers can show an error banner + retry.
        if (!cancelled) setGalleryError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => { if (!cancelled) setGalleryLoading(false); });
    return () => { cancelled = true; };
  }, [itemId, isDraft]);

  const handleGalleryUpload = useCallback(async (source: 'camera' | 'gallery', label?: string) => {
    if (!itemId || isDraft) return;
    setImageUploading(true);
    try {
      const url = await pickAndUpload(source);
      if (url && itemId) {
        const result = await collectorsApi.uploadItemImage(itemId, url, label || undefined);
        setGalleryImages((prev) => [...prev, result]);
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
        showToast({ message: 'Photo added', type: 'success' });
      }
    } catch (err) {
      logger.error('[useItemGallery] upload error:', err);
      showToast({ message: 'Failed to upload photo', type: 'error' });
    } finally {
      setImageUploading(false);
      setPendingLabel(null);
    }
  }, [itemId, isDraft, pickAndUpload, settings.hapticsEnabled]);

  const handleGalleryDelete = useCallback(async (imageId: string) => {
    if (!itemId) return;
    try {
      await collectorsApi.deleteItemImage(itemId, imageId);
      setGalleryImages((prev) => prev.filter((img) => img.id !== imageId));
      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Photo removed', type: 'info' });
    } catch (err) {
      logger.error('[useItemGallery] delete error:', err);
      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
      showToast({ message: 'Failed to remove photo', type: 'error' });
    }
  }, [itemId, settings.hapticsEnabled]);

  const handlePhotoUpload = useCallback(async (source: 'camera' | 'gallery') => {
    if (!isDraft && itemId) {
      handleGalleryUpload(source, pendingLabel || undefined);
      return;
    }
    const url = await pickAndUpload(source);
    if (url) setUserPhoto(url);
  }, [isDraft, itemId, handleGalleryUpload, pendingLabel, pickAndUpload]);

  const showLabelPicker = useCallback((callback: (label: string | null) => void) => {
    const options = ['No Label', ...IMAGE_LABELS.map((l) => LABEL_DISPLAY[l])];
    showActionSheet('Choose Photo Label', options, (index) => {
      if (index === 0) callback(null);
      else callback(IMAGE_LABELS[index - 1]);
    });
  }, []);

  const showPhotoSourcePicker = useCallback(() => {
    const doUpload = (source: 'camera' | 'gallery') => {
      if (!isDraft && itemId) {
        showLabelPicker((label) => {
          setPendingLabel(label);
          handleGalleryUpload(source, label || undefined);
        });
      } else {
        handlePhotoUpload(source);
      }
    };
    showActionSheet('Add Photo', ['Take Photo', 'Choose from Library'], (index) => {
      doUpload(index === 0 ? 'camera' : 'gallery');
    });
  }, [isDraft, itemId, handleGalleryUpload, handlePhotoUpload, showLabelPicker]);

  return {
    userPhoto, setUserPhoto,
    zoomVisible, setZoomVisible,
    zoomImageUri, setZoomImageUri,
    galleryImages, setGalleryImages,
    galleryLoading,
    galleryError,
    galleryActiveIndex, setGalleryActiveIndex,
    imageUploading,
    pendingLabel, setPendingLabel,
    flatListRef,
    displayImageUri,
    effectiveGalleryImages,
    photoUploading, photoError, userPhotoUrl,
    handleGalleryUpload,
    handleGalleryDelete,
    handlePhotoUpload,
    showPhotoSourcePicker,
    showLabelPicker,
    IMAGE_LABELS,
    LABEL_DISPLAY,
  };
}
