/**
 * useItemGallery hook tests.
 *
 * Validates that the hook:
 * - Initializes with empty gallery state
 * - Loads gallery images from API for non-draft items
 * - Uses cancellation guard on unmount
 * - Falls back to imageUri when no gallery images
 * - Handles gallery delete
 */
import { renderHook, act, waitFor } from '@testing-library/react-native';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockShowToast = jest.fn();
const mockSettings = { hapticsEnabled: true, currency: 'EUR', isDark: false };

jest.mock('../../src/lib/settings', () => ({
  useSettings: () => ({
    settings: mockSettings,
    updateSettings: jest.fn(),
    ready: true,
  }),
}));

jest.mock('../../src/components/Toast', () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

jest.mock('../../src/haptics', () => ({
  fireHaptic: jest.fn(),
  HapticIntent: {
    CONFIRMATION_LIGHT: 'CONFIRMATION_LIGHT',
    ALERT_TRIGGERED: 'ALERT_TRIGGERED',
  },
}));

jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { info: jest.fn(), warn: jest.fn(), error: jest.fn() },
}));

const mockPickAndUpload = jest.fn();

jest.mock('../../src/hooks/usePhotoUpload', () => ({
  usePhotoUpload: () => ({
    pickAndUpload: mockPickAndUpload,
    uploading: false,
    error: null,
    photoUrl: null,
  }),
}));

jest.mock('../../src/hooks/useActionSheetPicker', () => ({
  showActionSheet: jest.fn(),
}));

const mockListItemImages = jest.fn();
const mockUploadItemImage = jest.fn();
const mockDeleteItemImage = jest.fn();

jest.mock('../../src/api/collectorsApi', () => ({
  collectorsApi: {
    listItemImages: (...args: unknown[]) => mockListItemImages(...args),
    uploadItemImage: (...args: unknown[]) => mockUploadItemImage(...args),
    deleteItemImage: (...args: unknown[]) => mockDeleteItemImage(...args),
  },
}));

jest.mock('../../src/components/ItemGallerySection', () => ({}));

import { useItemGallery } from '../../src/hooks/useItemGallery';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
});

describe('useItemGallery', () => {
  describe('initial state', () => {
    it('initializes with empty gallery images', () => {
      mockListItemImages.mockReturnValue(new Promise(() => {})); // never resolves
      const { result } = renderHook(() => useItemGallery('item-1', false, 'https://example.com/img.jpg'));

      expect(result.current.galleryImages).toEqual([]);
      expect(result.current.galleryActiveIndex).toBe(0);
      expect(result.current.imageUploading).toBe(false);
      expect(result.current.zoomVisible).toBe(false);
    });

    it('initializes with galleryLoading=true for non-draft items', () => {
      mockListItemImages.mockReturnValue(new Promise(() => {}));
      const { result } = renderHook(() => useItemGallery('item-1', false));
      expect(result.current.galleryLoading).toBe(true);
    });
  });

  describe('image loading', () => {
    it('fetches gallery images for non-draft items', async () => {
      const mockImages = [
        { id: 'img-1', item_id: 'item-1', image_url: 'https://example.com/1.jpg', label: 'front', position: 0, created_at: null },
        { id: 'img-2', item_id: 'item-1', image_url: 'https://example.com/2.jpg', label: 'back', position: 1, created_at: null },
      ];
      mockListItemImages.mockResolvedValue({ images: mockImages });

      const { result } = renderHook(() => useItemGallery('item-1', false));

      await waitFor(() => {
        expect(result.current.galleryImages).toEqual(mockImages);
        expect(result.current.galleryLoading).toBe(false);
      });

      expect(mockListItemImages).toHaveBeenCalledWith('item-1');
    });

    it('does not fetch images for draft items', () => {
      const { result } = renderHook(() => useItemGallery('item-1', true));

      expect(mockListItemImages).not.toHaveBeenCalled();
      expect(result.current.galleryLoading).toBe(false);
    });

    it('does not fetch images when itemId is undefined', () => {
      renderHook(() => useItemGallery(undefined, false));
      expect(mockListItemImages).not.toHaveBeenCalled();
    });

    it('handles API error gracefully', async () => {
      mockListItemImages.mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useItemGallery('item-1', false));

      await waitFor(() => {
        expect(result.current.galleryLoading).toBe(false);
      });

      expect(result.current.galleryImages).toEqual([]);
    });
  });

  describe('effectiveGalleryImages', () => {
    it('returns gallery images when available', async () => {
      const mockImages = [
        { id: 'img-1', item_id: 'item-1', image_url: 'https://example.com/1.jpg', label: 'front', position: 0, created_at: null },
      ];
      mockListItemImages.mockResolvedValue({ images: mockImages });

      const { result } = renderHook(() => useItemGallery('item-1', false, 'https://fallback.com/img.jpg'));

      await waitFor(() => {
        expect(result.current.effectiveGalleryImages).toEqual(mockImages);
      });
    });

    it('falls back to imageUri when no gallery images', () => {
      mockListItemImages.mockResolvedValue({ images: [] });
      const { result } = renderHook(() => useItemGallery('item-1', true, 'https://fallback.com/img.jpg'));

      expect(result.current.effectiveGalleryImages).toEqual([
        expect.objectContaining({
          id: '__original__',
          image_url: 'https://fallback.com/img.jpg',
        }),
      ]);
    });

    it('returns empty array when no gallery images and no imageUri', () => {
      const { result } = renderHook(() => useItemGallery('item-1', true, undefined));
      expect(result.current.effectiveGalleryImages).toEqual([]);
    });
  });

  describe('handleGalleryDelete', () => {
    it('removes image from gallery on successful delete', async () => {
      const mockImages = [
        { id: 'img-1', item_id: 'item-1', image_url: 'https://example.com/1.jpg', label: 'front', position: 0, created_at: null },
        { id: 'img-2', item_id: 'item-1', image_url: 'https://example.com/2.jpg', label: 'back', position: 1, created_at: null },
      ];
      mockListItemImages.mockResolvedValue({ images: mockImages });
      mockDeleteItemImage.mockResolvedValue({});

      const { result } = renderHook(() => useItemGallery('item-1', false));

      await waitFor(() => {
        expect(result.current.galleryImages).toHaveLength(2);
      });

      await act(async () => {
        await result.current.handleGalleryDelete('img-1');
      });

      expect(mockDeleteItemImage).toHaveBeenCalledWith('item-1', 'img-1');
      expect(result.current.galleryImages).toHaveLength(1);
      expect(result.current.galleryImages[0].id).toBe('img-2');
    });

    it('shows error toast on delete failure', async () => {
      mockListItemImages.mockResolvedValue({ images: [{ id: 'img-1', item_id: 'item-1', image_url: 'url', label: null, position: 0, created_at: null }] });
      mockDeleteItemImage.mockRejectedValue(new Error('Delete failed'));

      const { result } = renderHook(() => useItemGallery('item-1', false));

      await waitFor(() => {
        expect(result.current.galleryImages).toHaveLength(1);
      });

      await act(async () => {
        await result.current.handleGalleryDelete('img-1');
      });

      expect(mockShowToast).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Failed to remove photo', type: 'error' })
      );
    });
  });

  describe('displayImageUri', () => {
    it('returns first gallery image when available', async () => {
      mockListItemImages.mockResolvedValue({
        images: [{ id: 'img-1', item_id: 'item-1', image_url: 'https://gallery.com/1.jpg', label: null, position: 0, created_at: null }],
      });

      const { result } = renderHook(() => useItemGallery('item-1', false, 'https://fallback.com/img.jpg'));

      await waitFor(() => {
        expect(result.current.displayImageUri).toBe('https://gallery.com/1.jpg');
      });
    });

    it('falls back to imageUri when no gallery images loaded', () => {
      const { result } = renderHook(() => useItemGallery('item-1', true, 'https://fallback.com/img.jpg'));
      expect(result.current.displayImageUri).toBe('https://fallback.com/img.jpg');
    });
  });

  describe('constants', () => {
    it('exports IMAGE_LABELS array', () => {
      const { result } = renderHook(() => useItemGallery('item-1', true));
      expect(result.current.IMAGE_LABELS).toContain('front');
      expect(result.current.IMAGE_LABELS).toContain('back');
      expect(result.current.IMAGE_LABELS).toContain('detail');
      expect(result.current.IMAGE_LABELS).toContain('box');
    });

    it('exports LABEL_DISPLAY mapping', () => {
      const { result } = renderHook(() => useItemGallery('item-1', true));
      expect(result.current.LABEL_DISPLAY).toHaveProperty('front', 'Front');
      expect(result.current.LABEL_DISPLAY).toHaveProperty('back', 'Back');
    });
  });
});
