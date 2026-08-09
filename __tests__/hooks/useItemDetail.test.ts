/**
 * useItemDetail hook tests.
 *
 * Validates that the hook:
 * - Initializes state from params
 * - Manages keyboard state
 * - Handles save notes/draft/edits
 * - Handles feedback submission
 * - Handles for-sale listing/unlisting
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
    JUDGMENT_LOCKED: 'JUDGMENT_LOCKED',
    ALERT_TRIGGERED: 'ALERT_TRIGGERED',
    CONFIRMATION_LIGHT: 'CONFIRMATION_LIGHT',
  },
}));

jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { info: jest.fn(), warn: jest.fn(), error: jest.fn() },
}));

const mockPersistQuickscanDraft = jest.fn();
const mockUpdateItem = jest.fn();
const mockSubmitFeedback = jest.fn();
const mockToggleForSale = jest.fn();
const mockListItems = jest.fn();

jest.mock('../../src/data', () => ({
  dataProvider: {
    persistQuickscanDraft: (...args: unknown[]) => mockPersistQuickscanDraft(...args),
    updateItem: (...args: unknown[]) => mockUpdateItem(...args),
    submitFeedback: (...args: unknown[]) => mockSubmitFeedback(...args),
    toggleForSale: (...args: unknown[]) => mockToggleForSale(...args),
    listItems: (...args: unknown[]) => mockListItems(...args),
  },
}));

jest.mock('../../src/lib/supabase', () => ({
  supabase: {
    from: () => ({
      select: () => ({
        eq: () => ({
          single: () => Promise.resolve({ data: null, error: null }),
        }),
      }),
      update: () => ({
        eq: () => Promise.resolve({ data: null, error: null }),
      }),
    }),
  },
}));

const mockGetPriceEvidence = jest.fn().mockResolvedValue(null);
const mockGetScarcityScores = jest.fn().mockResolvedValue({ items: [] });
const mockMarketplaceComps = jest.fn().mockResolvedValue({ comps: [] });
const mockSubmitVerifiedSale = jest.fn().mockResolvedValue({});

jest.mock('../../src/api/collectorsApi', () => ({
  collectorsApi: {
    getPriceEvidence: (...args: unknown[]) => mockGetPriceEvidence(...args),
    getScarcityScores: (...args: unknown[]) => mockGetScarcityScores(...args),
    marketplaceComps: (...args: unknown[]) => mockMarketplaceComps(...args),
    submitVerifiedSale: (...args: unknown[]) => mockSubmitVerifiedSale(...args),
  },
}));

jest.mock('expo-router', () => ({
  router: { replace: jest.fn(), push: jest.fn() },
}));

// Capture Keyboard listener callbacks
let keyboardShowCallback: ((e: { endCoordinates: { height: number } }) => void) | null = null;
let keyboardHideCallback: (() => void) | null = null;

// Patch Keyboard.addListener to capture callbacks (without replacing the full RN module)
jest.mock('react-native/Libraries/Components/Keyboard/Keyboard', () => ({
  __esModule: true,
  default: {
    addListener: jest.fn((event: string, cb: (...args: unknown[]) => void) => {
      if (event === 'keyboardWillShow') keyboardShowCallback = cb as typeof keyboardShowCallback;
      if (event === 'keyboardWillHide') keyboardHideCallback = cb as typeof keyboardHideCallback;
      return { remove: jest.fn() };
    }),
    dismiss: jest.fn(),
  },
}));

import { useItemDetail } from '../../src/hooks/useItemDetail';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const defaultParams = {
  id: 'item-1',
  isDraft: false,
  initialName: 'Charizard Base Set',
  initialCategory: 'pokemon_tcg',
  initialCollection: 'My Collection',
  initialCondition: 'Near Mint',
  initialValue: '350',
  initialNotes: 'Some notes',
  imageUri: 'https://example.com/image.jpg',
  categorySlug: 'pokemon_tcg',
  q50: '300',
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
  mockListItems.mockResolvedValue([]);
  keyboardShowCallback = null;
  keyboardHideCallback = null;
});

afterEach(() => {
  jest.useRealTimers();
});

describe('useItemDetail', () => {
  describe('initial state', () => {
    it('initializes edit state from params', () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));

      expect(result.current.editableName).toBe('Charizard Base Set');
      expect(result.current.editableCategory).toBe('pokemon_tcg');
      expect(result.current.editableCollection).toBe('My Collection');
      expect(result.current.editableCondition).toBe('Near Mint');
      expect(result.current.editableValue).toBe('350');
      expect(result.current.notes).toBe('Some notes');
    });

    it('initializes with isEditing=false', () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));
      expect(result.current.isEditing).toBe(false);
    });

    it('initializes save states as idle', () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));
      expect(result.current.savingNotes).toBe(false);
      expect(result.current.savingDraft).toBe(false);
      expect(result.current.saveError).toBeNull();
    });

    it('initializes keyboard state as hidden', () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));
      expect(result.current.keyboardVisible).toBe(false);
      expect(result.current.keyboardHeight).toBe(0);
    });

    it('initializes for-sale state as not for sale', () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));
      expect(result.current.isForSale).toBe(false);
      expect(result.current.askingPriceValue).toBe('');
      expect(result.current.forSaleLoading).toBe(false);
    });
  });

  describe('keyboard state', () => {
    it('updates keyboardVisible and keyboardHeight on keyboard show', () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));

      expect(keyboardShowCallback).not.toBeNull();

      act(() => {
        keyboardShowCallback!({ endCoordinates: { height: 336 } });
      });

      expect(result.current.keyboardVisible).toBe(true);
      expect(result.current.keyboardHeight).toBe(336);
    });

    it('resets keyboard state on keyboard hide', () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));

      act(() => {
        keyboardShowCallback!({ endCoordinates: { height: 336 } });
      });
      expect(result.current.keyboardVisible).toBe(true);

      act(() => {
        keyboardHideCallback!();
      });
      expect(result.current.keyboardVisible).toBe(false);
      expect(result.current.keyboardHeight).toBe(0);
    });
  });

  describe('onSaveNotes', () => {
    // This used to assert `message: 'Notes saved locally'` off a 300ms
    // setTimeout that wrote NOTHING — a test pinning a stub, so it stayed
    // green while every note a user typed was lost on unmount. It now
    // asserts the write actually happens.
    it('persists the note to the item', async () => {
      mockUpdateItem.mockResolvedValue({ id: 'item-1' });
      const { result } = renderHook(() => useItemDetail(defaultParams));

      await act(async () => {
        await result.current.onSaveNotes();
      });

      expect(mockUpdateItem).toHaveBeenCalledWith('item-1', { notes: 'Some notes' });
      expect(result.current.savingNotes).toBe(false);
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Notes saved', type: 'success' })
      );
    });

    it('reports failure instead of claiming success', async () => {
      // The whole point of the rewrite: never toast success on a failed write.
      mockUpdateItem.mockRejectedValue(new Error('network down'));
      const { result } = renderHook(() => useItemDetail(defaultParams));

      await act(async () => {
        await result.current.onSaveNotes();
      });

      expect(result.current.savingNotes).toBe(false);
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'error' })
      );
    });

    it('does not pretend to save a draft', async () => {
      // A draft has no items row to write to.
      const { result } = renderHook(() =>
        useItemDetail({ ...defaultParams, isDraft: true, id: undefined }),
      );

      await act(async () => {
        await result.current.onSaveNotes();
      });

      expect(mockUpdateItem).not.toHaveBeenCalled();
    });
  });

  describe('onSaveDraft', () => {
    it('calls persistQuickscanDraft and shows success toast', async () => {
      mockPersistQuickscanDraft.mockResolvedValue({
        id: 'new-id',
        title: 'Charizard Base Set',
        categoryId: 'pokemon_tcg',
        imageUrl: 'https://example.com/image.jpg',
      });

      const { result } = renderHook(() =>
        useItemDetail({ ...defaultParams, isDraft: true })
      );

      await act(async () => {
        await result.current.onSaveDraft();
      });

      expect(mockPersistQuickscanDraft).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Charizard Base Set',
          categoryId: 'pokemon_tcg',
        })
      );
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Item saved to collection', type: 'success' })
      );
    });

    it('does nothing when isDraft is false', async () => {
      const { result } = renderHook(() =>
        useItemDetail({ ...defaultParams, isDraft: false })
      );

      await act(async () => {
        await result.current.onSaveDraft();
      });

      expect(mockPersistQuickscanDraft).not.toHaveBeenCalled();
    });

    it('sets saveError on failure', async () => {
      mockPersistQuickscanDraft.mockRejectedValue(new Error('Network failure'));

      const { result } = renderHook(() =>
        useItemDetail({ ...defaultParams, isDraft: true })
      );

      await act(async () => {
        await result.current.onSaveDraft();
      });

      expect(result.current.saveError).toBe('Network failure');
      expect(result.current.savingDraft).toBe(false);
    });
  });

  describe('onSaveEdits', () => {
    it('calls updateItem and shows success toast', async () => {
      mockUpdateItem.mockResolvedValue({});

      const { result } = renderHook(() => useItemDetail(defaultParams));

      act(() => {
        result.current.setIsEditing(true);
      });

      await act(async () => {
        await result.current.onSaveEdits();
      });

      expect(mockUpdateItem).toHaveBeenCalledWith('item-1', {
        name: 'Charizard Base Set',
        category: 'pokemon_tcg',
      });
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Changes saved', type: 'success' })
      );
      expect(result.current.isEditing).toBe(false);
    });

    it('does nothing for draft items', async () => {
      const { result } = renderHook(() =>
        useItemDetail({ ...defaultParams, isDraft: true })
      );

      await act(async () => {
        await result.current.onSaveEdits();
      });

      expect(mockUpdateItem).not.toHaveBeenCalled();
    });
  });

  describe('handleListForSale', () => {
    it('lists item for sale with valid price', async () => {
      mockToggleForSale.mockResolvedValue({});

      const { result } = renderHook(() => useItemDetail(defaultParams));

      act(() => {
        result.current.setAskingPriceValue('250');
      });

      await act(async () => {
        await result.current.handleListForSale();
      });

      expect(mockToggleForSale).toHaveBeenCalledWith('item-1', true, 250);
      expect(result.current.isForSale).toBe(true);
    });

    it('shows error toast for invalid price', async () => {
      const { result } = renderHook(() => useItemDetail(defaultParams));

      act(() => {
        result.current.setAskingPriceValue('abc');
      });

      await act(async () => {
        await result.current.handleListForSale();
      });

      expect(mockToggleForSale).not.toHaveBeenCalled();
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Enter a valid asking price', type: 'error' })
      );
    });
  });

  describe('handleUnlist', () => {
    it('unlists item and clears asking price', async () => {
      mockToggleForSale.mockResolvedValue({});

      const { result } = renderHook(() => useItemDetail(defaultParams));

      // First mark as for sale
      act(() => {
        result.current.setIsForSale(true);
        result.current.setAskingPriceValue('250');
      });

      await act(async () => {
        await result.current.handleUnlist();
      });

      expect(mockToggleForSale).toHaveBeenCalledWith('item-1', false);
      expect(result.current.isForSale).toBe(false);
      expect(result.current.askingPriceValue).toBe('');
    });
  });

  describe('evidence data', () => {
    it('fetches evidence data for non-draft items', async () => {
      mockGetPriceEvidence.mockResolvedValue({
        explanation: 'Based on 5 recent sales',
        evidence_summary: { sources: [], total_comps: 5 },
        evidence_hit_ids: [],
        prediction_at: '2026-03-15',
      });

      renderHook(() => useItemDetail(defaultParams));

      await waitFor(() => {
        expect(mockGetPriceEvidence).toHaveBeenCalledWith('item-1');
      });
    });

    it('does not fetch evidence for draft items', async () => {
      renderHook(() => useItemDetail({ ...defaultParams, isDraft: true }));

      // Let async effects run
      await act(async () => {
        jest.advanceTimersByTime(0);
      });

      expect(mockGetPriceEvidence).not.toHaveBeenCalled();
    });
  });
});
